"""Prepare an offline, frozen diagnostic batch; live execution requires --run-live.

From the repository root:
  backend/.venv/Scripts/python.exe backend/scripts/validate_plumbing_vision.py
The default only writes a plan. No provider client is created without --run-live.
This standalone runner does not save projects or change production configuration.
"""
import argparse
import asyncio
import base64
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time
from unittest.mock import patch

import httpx
from dotenv import dotenv_values
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app import plumbing_vision as vision

OUT = ROOT / 'backend/datasets/gemini-validation-2026-10-25'
MAX_REQUESTS = 10
SOURCE = 'backend/tests/fixtures/plans/Data Set/Plumbingplan/IMAGE/'
SAMPLES = [
    ('cafeteria', SOURCE + '01.png', {'WC': 2, 'LAV': 2},
     'Previously exposed; owner-confirmed counts, approximate box boundaries.'),
    ('restroom', SOURCE + '02.png', {'WC': 11, 'LAV': 12},
     'Previously exposed; owner-confirmed counts; exclude urinals and floor drains.'),
    ('residential', SOURCE + '03.jpg', {'WC': 1, 'LAV': 1},
     'Previously exposed, visually reviewed draft; faint scan, kitchen sink excluded.'),
    ('nist_single_story', 'backend/datasets/nist-plumbing/annotation-crops/page-03-sanitary.png',
     {'WC': 1, 'LAV': 1},
     'Selected sanitary view, not full sheet; exposed research family, draft visual counts. '
     'Exclude bathtub P-3, kitchen sink P-4, washer P-5 and drains.'),
]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_path(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('Sample must remain inside the repository.')
    return path


def prepare(primary, alternate):
    if primary == alternate or any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', m)
                                   for m in (primary, alternate)):
        raise ValueError('Choose two distinct explicit Gemini model IDs.')
    samples = []
    for name, relative, counts, note in SAMPLES:
        raw = checked_path(relative).read_bytes()
        payload = base64.b64decode(vision.image_payload(raw))
        with Image.open(io.BytesIO(raw)) as original, Image.open(io.BytesIO(payload)) as sent:
            samples.append(dict(id=name, path=relative, source_sha256=digest(raw),
                original_dimensions=list(original.size), sent_dimensions=list(sent.size),
                sent_sha256=digest(payload), reference_counts=counts, review_note=note))
    jobs = []
    for sample in samples:
        for repeat in range(3 if sample['id'] in ('cafeteria', 'restroom') else 1):
            jobs.append(dict(sample=sample['id'], model=primary, repeat=repeat + 1))
    jobs += [dict(sample=s, model=alternate, repeat=1) for s in ('cafeteria', 'restroom')]
    assert len(jobs) == MAX_REQUESTS
    return dict(version=1, provider='gemini', max_requests=MAX_REQUESTS,
        implementation_sha256=digest(Path(vision.__file__).read_bytes()),
        prompt_version=vision.PROMPT_VERSION, prompt=vision.PROMPT,
        prompt_sha256=digest(vision.PROMPT.encode()), schema_sha256=digest(
            json.dumps(vision.SCHEMA, sort_keys=True).encode()),
        settings=dict(temperature=0, maxOutputTokens=24000, timeout_seconds=30),
        samples=samples, jobs=jobs,
        limits='No retries, no automatic fallbacks, no OpenRouter, no project writes. '
               'Draft location review required; matching totals do not prove accuracy. '
               'No independent held-out accuracy claim. Cost/quotas not yet verified.')


class RequestStages:
    """Only retain fixed event names/timings; never retain transport info objects."""
    EVENTS = {
        'connection.connect_tcp': 'connecting',
        'connection.start_tls': 'tls_handshake',
        'http11.send_request_headers': 'sending_headers',
        'http11.send_request_body': 'uploading',
        'http11.receive_response_headers': 'waiting_for_headers',
        'http11.receive_response_body': 'reading_body',
        'http2.send_request_headers': 'sending_headers',
        'http2.send_request_body': 'uploading',
        'http2.receive_response_headers': 'waiting_for_headers',
        'http2.receive_response_body': 'reading_body',
    }

    def __init__(self):
        self.started = time.perf_counter()
        self.stage = 'before_transport'
        self.events = []
        self.status = None
        self.body_bytes = 0

    def mark(self, stage, event):
        self.stage = stage
        if len(self.events) < 80:
            self.events.append(dict(event=event, elapsed_seconds=round(
                time.perf_counter() - self.started, 4)))

    async def trace(self, name, info):
        # info may contain credentials, headers, network addresses or exceptions.
        # Deliberately never inspect or serialize it.
        base, _, state = name.rpartition('.')
        if base not in self.EVENTS or state not in ('started', 'complete', 'failed'):
            return
        stage = self.EVENTS[base]
        if state == 'complete' and stage == 'uploading':
            stage = 'waiting_for_headers'
        self.mark(stage, name)

    def snapshot(self):
        return dict(last_stage=self.stage, events=self.events,
                    response_status=self.status, received_body_bytes=self.body_bytes)


class ObservedClient:
    """Wrap the runner's client without changing production request/payload code."""
    def __init__(self, client, stages):
        self.client, self.stages = client, stages

    @asynccontextmanager
    async def stream(self, *args, **kwargs):
        extensions = dict(kwargs.pop('extensions', {}) or {})
        extensions['trace'] = self.stages.trace
        self.stages.mark('request_started', 'request_started')
        async with self.client.stream(*args, extensions=extensions, **kwargs) as response:
            self.stages.status = response.status_code
            self.stages.mark('response_headers_received', 'response_headers_received')
            yield ObservedResponse(response, self.stages)


class ObservedResponse:
    def __init__(self, response, stages):
        self.response, self.stages = response, stages

    def raise_for_status(self):
        self.response.raise_for_status()

    async def aiter_bytes(self):
        self.stages.mark('reading_body', 'body_read_started')
        async for chunk in self.response.aiter_bytes():
            self.stages.body_bytes += len(chunk)
            yield chunk
        self.stages.mark('body_complete', 'body_read_complete')


async def run_job(client, model, encoded):
    """Exercise the production request/parser while retaining diagnostic metadata."""
    captured = {}
    stages = RequestStages()
    original_post = vision.post_json

    async def capture(*args, **kwargs):
        body = await original_post(ObservedClient(args[0], stages), *args[1:], **kwargs)
        stages.mark('response_json_complete', 'response_json_complete')
        for key in ('modelVersion', 'usageMetadata', 'responseId'):
            if key in body:
                captured[key] = body[key]
        return body

    started = time.perf_counter()
    try:
        with patch.object(vision, 'post_json', capture):
            response_text = await asyncio.wait_for(
                vision.call_model(client, 'gemini', model, encoded), timeout=30)
        captured['response_text'] = response_text
        fixtures, limitations = vision.parse_proposals(response_text)
        captured.update(outcome='proposed', fixtures=[f.model_dump() for f in fixtures],
                        counts=dict(Counter(f.fixture_class for f in fixtures)), limitations=limitations)
    except httpx.HTTPStatusError as exc:
        captured.update(outcome='provider_error', http_status=exc.response.status_code)
    except (TimeoutError, httpx.TimeoutException) as exc:
        captured['outcome'] = 'timeout'
        captured['timeout_kind'] = next((label for cls, label in (
            (httpx.ConnectTimeout, 'connect_timeout'), (httpx.ReadTimeout, 'read_timeout'),
            (httpx.WriteTimeout, 'write_timeout'), (httpx.PoolTimeout, 'pool_timeout'),
            (httpx.TimeoutException, 'http_timeout')) if isinstance(exc, cls)), 'overall_deadline')
        captured['timeout_stage'] = stages.stage
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError):
        captured['outcome'] = 'transport_or_invalid_response'
    captured['elapsed_seconds'] = round(time.perf_counter() - started, 3)
    captured['requested_model'] = model
    captured['transport'] = stages.snapshot()
    return captured


async def execute(plan, directory, request_limit=MAX_REQUESTS):
    """One serial attempt per job; fail closed on drift and never resume/retry."""
    if not 1 <= len(plan['jobs']) <= MAX_REQUESTS:
        raise ValueError('Request budget exceeded.')
    if type(request_limit) is not int or not 1 <= request_limit <= MAX_REQUESTS:
        raise ValueError('Request limit must be between one and ten.')
    primary, alternate = plan['jobs'][0]['model'], plan['jobs'][-1]['model']
    if prepare(primary, alternate) != plan:
        raise ValueError('Plan, source images or production prompt/settings changed; prepare and review again.')
    if not vision.os.getenv('GEMINI_API_KEY'):
        raise ValueError('Server-side GEMINI_API_KEY is missing.')
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'approved-plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    (directory / 'execution-limit.json').write_text(json.dumps(
        {'request_limit': request_limit, 'selected_jobs': plan['jobs'][:request_limit]}, indent=2) + '\n', encoding='utf-8')
    samples = {s['id']: s for s in plan['samples']}
    async with httpx.AsyncClient(timeout=30, follow_redirects=False, trust_env=False) as client:
        for index, job in enumerate(plan['jobs'][:request_limit], 1):
            raw = checked_path(samples[job['sample']]['path']).read_bytes()
            record = await run_job(client, job['model'], vision.image_payload(raw))
            record.update(job=job, sample=samples[job['sample']], utc=datetime.now(timezone.utc).isoformat())
            # Local diagnostic evidence; never log keys, receipts, upstream error bodies or URLs.
            (directory / f'{index:02d}.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
            print(f"{index}/{min(request_limit, len(plan['jobs']))}: {job['sample']} {record['outcome']}")
            # Do not continue spending requests when account/provider availability is in doubt.
            if record.get('http_status') in (401, 403, 404, 429) or record['outcome'] != 'proposed':
                print('Stopped after unsuccessful request; no retry or fallback was made.')
                break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--primary', default='gemini-3.8-flash')
    parser.add_argument('--alternate', default='gemini-2.5-flash')
    parser.add_argument('--plan', type=Path, default=OUT / 'plan.json')
    parser.add_argument('--run-live', action='store_true', help='Sends images; use only after explicit batch approval.')
    parser.add_argument('--request-limit', type=int, default=MAX_REQUESTS,
                        help='Reduce live execution to the first N planned jobs, maximum ten. No retries.')
    args = parser.parse_args()
    if args.run_live:
        # Load credentials only in explicitly selected live mode; never print their values.
        for key, value in dotenv_values(ROOT / 'backend/.env').items():
            if key == 'GEMINI_API_KEY' and value:
                vision.os.environ[key] = value
        plan = json.loads(args.plan.read_text(encoding='utf-8'))
        directory = OUT / ('run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        asyncio.run(execute(plan, directory, args.request_limit))
    else:
        plan = prepare(args.primary, args.alternate)
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        args.plan.write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
        print(f"Offline plan prepared: {len(plan['jobs'])} maximum requests, {len(plan['samples'])} samples. No network calls.")


if __name__ == '__main__':
    main()
