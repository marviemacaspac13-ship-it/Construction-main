"""Trace reviewed misses through the unchanged production tiled OCR reader.

Captures RapidOCR proposals immediately before its recognition-confidence filter,
then the existing exact-string merges and final tag/legend filtering. All hooks
forward original calls unchanged and are scoped to this offline process.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from math import hypot
from pathlib import Path
import re
import sys
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.extract import ocr, tags
from app.takeoff.constants import FIXTURE_TAG_PATTERNS


def baseline_normalise(text):
    """Frozen pre-fix tokenizer, so this historical diagnostic stays reproducible."""
    return text.upper().strip(".,*+-:;_ ")


def canonical(text):
    text = baseline_normalise(text)
    return next((tag for tag, pattern in FIXTURE_TAG_PATTERNS.items()
                 if re.fullmatch(pattern, text, re.I)), None)


def near(box, target):
    return hypot(box['cx'] - target['cx'], box['cy'] - target['cy']) <= 8


def covers(box, target):
    quad = box.get('quad')
    return bool(quad and cv2.pointPolygonTest(np.asarray(quad, np.float32),
                (float(target['cx']), float(target['cy'])), False) >= 0)


def diagnose(target, proposals, before_merge, merged, final):
    """Attribute misses conservatively; absence at this hook is not no heatmap ink."""
    correct = lambda b: near(b, target) and canonical(b['text']) == target['tag']
    local = [p for p in proposals if near(p, target) or covers(p, target)]
    if any(correct(b) for b in final):
        reason = 'recovered'
    elif any(correct(b) for b in merged):
        reason = 'legend_filter'
    elif any(correct(b) for b in before_merge):
        reason = 'exact_string_merge'
    elif any(near(b, target) and canonical(re.sub(r'\s+', '', b['text'])) == target['tag']
             for b in merged):
        # Diagnostic only: do not introduce whitespace repair into production.
        reason = 'tag_parser_internal_whitespace'
    elif any(correct(p) and not p['passes_confidence'] for p in local):
        reason = 'recognition_confidence_filter'
    elif any(correct(p) and p['passes_confidence'] for p in local):
        reason = 'coordinate_or_normalization_review_required'
    elif local:
        reason = 'recognition_or_text_grouping'
    else:
        reason = 'no_local_detector_proposal'
    return dict(target=target, reason=reason, local_proposals=local)


def render_review(result, image, output):
    """Show each miss beside its strongest local pre-filter OCR proposal."""
    (output / 'overlays').mkdir(exist_ok=True)
    canvas = np.full((4 * 205, 4 * 340, 3), 255, np.uint8)
    for index, diagnosis in enumerate(result['misses']):
        target = diagnosis['target']
        x, y = round(target['cx']), round(target['cy'])
        x0, y0 = max(0, x - 30), max(0, y - 18)
        x1, y1 = min(image.shape[1], x + 30), min(image.shape[0], y + 18)
        crop = cv2.resize(image[y0:y1, x0:x1], None, fx=4, fy=4,
                          interpolation=cv2.INTER_NEAREST)
        local = sorted(diagnosis['local_proposals'], key=lambda p: -p['score'])
        if local:
            proposal = local[0]
            quad = np.asarray([[(px-x0)*4, (py-y0)*4] for px, py in proposal['quad']], np.int32)
            cv2.polylines(crop, [quad], True, (0, 150, 0), 1)
            label = f"OCR {proposal['text']!r}  score {proposal['score']:.3f}"
        else:
            label = 'No local detector proposal'
        cv2.drawMarker(crop, ((x-x0)*4, (y-y0)*4), (0, 0, 220), cv2.MARKER_CROSS, 9, 1)
        left, top = (index % 4) * 340, (index // 4) * 205
        canvas[top+54:top+54+crop.shape[0], left+8:left+8+crop.shape[1]] = crop
        for text, offset in [(target['id'], 19), (label, 40)]:
            cv2.putText(canvas, text, (left+8, top+offset), cv2.FONT_HERSHEY_SIMPLEX,
                        .46, (30, 30, 30), 1, cv2.LINE_AA)
    cv2.imwrite(str(output / 'overlays/missed-tag-trace.png'), canvas)


class Trace:
    def __init__(self, image):
        self.image = image
        self.engine = ocr._engine()
        self.context = None
        self.proposals = []
        self.calls = []
        self.merges = []
        self.original_filter = self.engine.filter_boxes_rec_by_score
        self.original_dedupe = ocr._dedupe
        self.original_region = tags.read_region
        self.original_array = tags.read_array

    def filtered(self, boxes, readings):
        context = self.context
        assert context is not None
        call = self.calls[-1]
        assert len(boxes) == len(readings)
        for quad, (text, confidence) in zip(boxes, readings):
            vertices = [(float(x), float(y)) for x, y in quad]
            if call['rotated']:
                vertices = [(y, context['height'] - 1 - x) for x, y in vertices]
            vertices = [(x + context['x'], y + context['y']) for x, y in vertices]
            self.proposals.append(dict(
                id=f"proposal-{len(self.proposals) + 1:04}", call_id=call['id'],
                source=context['source'], rotated=call['rotated'], text=str(text),
                score=float(confidence), passes_confidence=float(confidence) >= self.engine.text_score,
                quad=vertices, cx=sum(x for x, _ in vertices) / 4,
                cy=sum(y for _, y in vertices) / 4))
        return self.original_filter(boxes, readings)

    def __call__(self, image):
        context = self.context
        rotated = context['pass'] == 1
        assert context['pass'] < 2
        self.calls.append(dict(id=len(self.calls) + 1, source=context['source'],
                               rotated=rotated, shape=list(image.shape)))
        context['pass'] += 1
        return self.engine(image)

    def region(self, image, x1, y1, x2, y2):
        self.context = dict(source=f'tile:{x1},{y1},{x2},{y2}', x=x1, y=y1,
                            height=y2 - y1, **{'pass': 0})
        return self.original_region(image, x1, y1, x2, y2)

    def array(self, image):
        self.context = dict(source='whole_page', x=0, y=0, height=image.shape[0], **{'pass': 0})
        return self.original_array(image)

    def merge(self, boxes):
        result = self.original_dedupe(boxes)
        kept_ids = {id(b) for b in result}
        removed = []
        for b in boxes:
            if id(b) in kept_ids:
                continue
            keeper = next(k for k in sorted(result, key=lambda k: -k.score)
                          if k.text == b.text and abs(k.cx-b.cx) <= ocr.DEDUPE_RADIUS
                          and abs(k.cy-b.cy) <= ocr.DEDUPE_RADIUS)
            removed.append(dict(dropped=asdict(b), kept=asdict(keeper)))
        self.merges.append(dict(input=[asdict(b) for b in boxes],
                                output=[asdict(b) for b in result], removed=removed))
        return result

    def run(self):
        with patch.object(ocr, '_engine', return_value=self), \
             patch.object(self.engine, 'filter_boxes_rec_by_score', side_effect=self.filtered), \
             patch.object(tags, 'read_region', side_effect=self.region), \
             patch.object(tags, 'read_array', side_effect=self.array), \
             patch.object(ocr, '_dedupe', side_effect=self.merge):
            merged = tags.read_tiled(self.image)
        # This tool explains the recorded pre-fix 16 misses. Use its tokenizer
        # explicitly instead of silently reinterpreting historical evidence.
        with patch.object(tags, 'normalise_tag', side_effect=baseline_normalise):
            counts = tags.count_tags(merged, FIXTURE_TAG_PATTERNS, self.image.shape)
        final = [dict(tag=tag, **asdict(box)) for tag, result in counts.items() for box in result.boxes]
        return merged, counts, final


def run(output):
    baseline_path = ROOT / 'datasets/tag-geometry-stage1/evidence.json'
    inventory_path = ROOT / 'datasets/tag-evidence-stage1/tag-inventory.json'
    baseline = next(r for r in json.loads(baseline_path.read_text()) if r['file'] == 'trace-02.png')
    inventory = next(r for r in json.loads(inventory_path.read_text())['images'] if r['file'] == baseline['file'])
    source = ROOT / 'datasets' / baseline['source']
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == baseline['sha256']
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    output.mkdir(parents=True, exist_ok=False)
    trace = Trace(image)
    merged, counts, final = trace.run()
    # Fail loudly if observing the pipeline altered the reproducible baseline.
    observed = [dict(id=f'tag-{i+1:03}', **o, review='unreviewed') for i, o in enumerate(final)]
    assert json.loads(json.dumps(observed)) == baseline['observations']
    assert dict(tags.tally(counts)) == baseline['before_counts']
    assert len(trace.calls) == 52 and len(trace.merges) == 2
    before_merge = [b for stage in trace.merges for b in stage['input']]
    diagnoses = [diagnose(t, trace.proposals, before_merge,
                         [asdict(b) for b in merged], final) for t in inventory['annotations']]
    misses = [d for d in diagnoses if d['reason'] != 'recovered']
    assert len(misses) == 16
    for d in misses:
        d['merge_events'] = [dict(stage=i, **event) for i, stage in enumerate(trace.merges)
                             for event in stage['removed'] if near(event['dropped'], d['target'])]
    result = dict(file=baseline['file'], baseline_unchanged=True,
                  summary=dict(Counter(d['reason'] for d in misses)), misses=misses,
                  all_targets=diagnoses,
                  provenance={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [source, baseline_path, inventory_path, Path(__file__),
                                        ROOT/'app/extract/ocr.py', ROOT/'app/extract/tags.py']},
                  scope='Frozen pre-spacing-fix tokenizer; same-agent development inventory; '
                  '8px center association or polygon covering center. '
                  'No local detector proposal means none after detector postprocessing; '
                  'raw detector heatmaps are not inspected. No production changes.',
                  text_score=trace.engine.text_score)
    render_review(result, image, output)
    for name, data in [('diagnosis.json', result), ('raw-trace.json', dict(calls=trace.calls,
                       proposals=trace.proposals, merges=trace.merges, final=final))]:
        (output/name).write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result['summary'], indent=2))
    for d in misses:
        print(d['target']['id'], d['reason'],
              [(p['text'], round(p['score'], 3), p['passes_confidence']) for p in d['local_proposals']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
