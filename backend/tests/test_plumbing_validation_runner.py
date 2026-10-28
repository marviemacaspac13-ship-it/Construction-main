"""Offline budget, evidence and fail-closed checks for the standalone runner."""
import asyncio
import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

spec = importlib.util.spec_from_file_location('validation_runner',
    Path(__file__).resolve().parents[1] / 'scripts/validate_plumbing_vision.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_offline_plan_never_contacts_provider(monkeypatch):
    post = AsyncMock(side_effect=AssertionError('Network is forbidden'))
    monkeypatch.setattr(runner.vision, 'post_json', post)
    plan = runner.prepare('primary', 'alternate')
    assert len(plan['jobs']) == 10
    assert len(plan['samples']) == 4
    assert sum(j['model'] == 'alternate' for j in plan['jobs']) == 2
    post.assert_not_called()


def test_provider_identity_usage_and_parser_evidence_are_retained(monkeypatch):
    text = json.dumps({'fixtures': [dict(id='a', fixture_class='WC',
        box_2d=[10, 10, 20, 20], uncertainty=None)], 'limitations': []})
    post = AsyncMock(return_value=dict(modelVersion='resolved-version',
        usageMetadata={'totalTokenCount': 123}, responseId='response-1',
        candidates=[dict(finishReason='STOP', content={'parts': [{'text': text}]})]))
    monkeypatch.setattr(runner.vision, 'post_json', post)
    monkeypatch.setenv('GEMINI_API_KEY', 'test-only')
    record = asyncio.run(runner.run_job(None, 'requested-alias', 'fake-image'))
    assert record['modelVersion'] == 'resolved-version'
    assert record['requested_model'] == 'requested-alias'
    assert record['usageMetadata']['totalTokenCount'] == 123
    assert record['counts'] == {'WC': 1}
    assert record['elapsed_seconds'] >= 0


def test_changed_plan_refused_before_network(tmp_path):
    plan = runner.prepare('primary', 'alternate')
    plan['samples'][0]['source_sha256'] = 'changed'
    with pytest.raises(ValueError, match='changed'):
        asyncio.run(runner.execute(plan, tmp_path / 'run'))
    assert not (tmp_path / 'run').exists()


def test_rate_limit_stops_batch_without_retry_or_key_in_output(tmp_path, monkeypatch):
    plan = runner.prepare('primary', 'alternate')
    monkeypatch.setenv('GEMINI_API_KEY', 'secret-test-value')
    request = httpx.Request('POST', 'https://example.invalid')
    response = httpx.Response(429, request=request, text='secret-test-value')
    post = AsyncMock(side_effect=httpx.HTTPStatusError('private upstream message',
        request=request, response=response))
    monkeypatch.setattr(runner.vision, 'post_json', post)
    out = tmp_path / 'run'
    asyncio.run(runner.execute(plan, out))
    assert post.await_count == 1
    assert len(list(out.glob('[0-9][0-9].json'))) == 1
    record = (out / '01.json').read_text()
    assert 'secret-test-value' not in record
    assert 'private upstream message' not in record
    assert json.loads(record)['http_status'] == 429


@pytest.mark.parametrize('failure,kind', [
    (TimeoutError(), 'overall_deadline'),
    (httpx.ConnectTimeout('private connect details'), 'connect_timeout'),
    (httpx.ReadTimeout('private read details'), 'read_timeout'),
    (httpx.WriteTimeout('private write details'), 'write_timeout'),
    (httpx.PoolTimeout('private pool details'), 'pool_timeout'),
])
def test_timeout_subtype_is_retained_without_exception_text(monkeypatch, failure, kind):
    monkeypatch.setattr(runner.vision, 'call_model', AsyncMock(side_effect=failure))
    record = asyncio.run(runner.run_job(None, 'diagnostic-only', 'not-sent'))
    assert record['outcome'] == 'timeout'
    assert record['timeout_kind'] == kind
    assert record['timeout_stage'] == 'before_transport'
    assert 'http_status' not in record
    assert 'private' not in json.dumps(record)


def test_stalled_body_retains_headers_progress_and_deadline_kind(monkeypatch):
    seen = []

    class SlowBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{'
            await asyncio.sleep(10)
            yield b'}'

    async def handler(request):
        seen.append('mock_headers_200')
        return httpx.Response(200, stream=SlowBody())

    original_wait = asyncio.wait_for

    async def short_deadline(awaitable, timeout):
        return await original_wait(awaitable, timeout=0.02)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await runner.run_job(client, 'diagnostic-only', 'not-sent')

    monkeypatch.setenv('GEMINI_API_KEY', 'test-only')
    monkeypatch.setattr(runner.asyncio, 'wait_for', short_deadline)
    record = asyncio.run(run())
    assert seen == ['mock_headers_200']
    assert record['outcome'] == 'timeout'
    assert record['transport']['response_status'] == 200
    assert record['transport']['received_body_bytes'] == 1
    assert record['timeout_stage'] == 'reading_body'
    assert record['timeout_kind'] == 'overall_deadline'
    assert 'modelVersion' not in record


@pytest.mark.parametrize('event,kind,stage', [
    ('connection.connect_tcp', httpx.ConnectTimeout, 'connecting'),
    ('connection.start_tls', httpx.ConnectTimeout, 'tls_handshake'),
    ('http11.send_request_body', httpx.WriteTimeout, 'uploading'),
    ('http11.receive_response_headers', httpx.ReadTimeout, 'waiting_for_headers'),
    ('http2.receive_response_headers', httpx.ReadTimeout, 'waiting_for_headers'),
])
def test_transport_stage_and_sensitive_info_filter(monkeypatch, event, kind, stage):
    async def handler(request):
        trace = request.extensions['trace']
        await trace('unknown.private.secret', {'password': 'secret-test-value'})
        await trace(event + '.started', {'headers': {'key': 'secret-test-value'}})
        raise kind('secret-test-value')

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await runner.run_job(client, 'diagnostic-only', 'not-sent')

    monkeypatch.setenv('GEMINI_API_KEY', 'secret-test-value')
    record = asyncio.run(run())
    assert record['timeout_stage'] == stage
    assert record['transport']['response_status'] is None
    serialized = json.dumps(record)
    assert 'secret-test-value' not in serialized
    assert 'unknown.private' not in serialized


def test_success_retains_body_and_provider_metadata_with_mock_transport(monkeypatch):
    text = json.dumps({'fixtures': [dict(id='a', fixture_class='WC',
        box_2d=[10, 10, 20, 20], uncertainty=None)], 'limitations': []})
    body = dict(modelVersion='resolved-version', usageMetadata={'totalTokenCount': 42},
        candidates=[dict(finishReason='STOP', content={'parts': [{'text': text}]})])

    async def handler(request):
        trace = request.extensions['trace']
        await trace('http11.send_request_body.complete', {})
        return httpx.Response(200, json=body)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await runner.run_job(client, 'diagnostic-only', 'not-sent')

    monkeypatch.setenv('GEMINI_API_KEY', 'test-only')
    record = asyncio.run(run())
    assert record['outcome'] == 'proposed'
    assert record['transport']['response_status'] == 200
    assert record['transport']['received_body_bytes'] > 0
    assert record['modelVersion'] == 'resolved-version'
    assert record['usageMetadata']['totalTokenCount'] == 42
    assert 'timeout_kind' not in record


def test_one_request_limit_stops_even_after_success(tmp_path, monkeypatch):
    plan = runner.prepare('primary', 'alternate')
    text = json.dumps({'fixtures': [dict(id='a', fixture_class='WC',
        box_2d=[10, 10, 20, 20], uncertainty=None)], 'limitations': []})
    call = AsyncMock(return_value=text)
    monkeypatch.setattr(runner.vision, 'call_model', call)
    monkeypatch.setenv('GEMINI_API_KEY', 'test-only')
    out = tmp_path / 'single'
    asyncio.run(runner.execute(plan, out, request_limit=1))
    assert call.await_count == 1
    assert len(list(out.glob('[0-9][0-9].json'))) == 1
    selection = json.loads((out / 'execution-limit.json').read_text())
    assert selection['selected_jobs'] == [plan['jobs'][0]]


@pytest.mark.parametrize('limit', [0, 11, True])
def test_invalid_request_limit_refused_before_execution(tmp_path, limit):
    with pytest.raises(ValueError, match='Request limit'):
        asyncio.run(runner.execute(runner.prepare('primary', 'alternate'), tmp_path / 'bad', limit))
    assert not (tmp_path / 'bad').exists()
