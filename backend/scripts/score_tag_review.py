"""Score a frozen tag inventory and stress-test the offline duplicate rule.

Tag-center associations are not fixture-object IoU metrics. Review is a
same-agent development audit, not an independent acceptance set.
"""
import argparse
from collections import Counter
import hashlib
import json
from math import hypot
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.probe_tag_duplicates import deduplicate


def score(truth, observations, radius):
    edges = sorted((hypot(t['cx'] - o['cx'], t['cy'] - o['cy']), i, j)
                   for i, t in enumerate(truth) for j, o in enumerate(observations)
                   if t['tag'] == o['tag']
                   and hypot(t['cx'] - o['cx'], t['cy'] - o['cy']) <= radius)
    used_truth, used_output = set(), set()
    for _, i, j in edges:
        if i not in used_truth and j not in used_output:
            used_truth.add(i)
            used_output.add(j)
    tp = len(used_truth)
    return dict(correct=tp, false_or_duplicate=len(observations) - tp,
                missed=len(truth) - tp,
                precision=tp / len(observations) if observations else None,
                recall=tp / len(truth) if truth else None,
                missed_ids=[t['id'] for i, t in enumerate(truth) if i not in used_truth])


def run(directory):
    evidence = json.loads((directory / 'evidence.json').read_text())
    inventory = json.loads((directory / 'tag-inventory.json').read_text())
    by_hash = {r['pixel_sha256']: r for r in evidence}
    rows = []
    for item in inventory['images']:
        original = by_hash[item['pixel_sha256']]['observations']
        candidate, removed = deduplicate(original)
        truth = item['annotations']
        radius = inventory['matching_policy']['maximum_center_distance_px']
        by_class = {}
        for tag in sorted({t['tag'] for t in truth} | {o['tag'] for o in original}):
            selected = [t for t in truth if t['tag'] == tag]
            by_class[tag] = dict(truth=len(selected),
                before=score(selected, [o for o in original if o['tag'] == tag], radius),
                candidate=score(selected, [o for o in candidate if o['tag'] == tag], radius))
        stress = []
        for scale in (1.0, 0.75, 0.5):
            perfect = [dict(t, cx=t['cx'] * scale, cy=t['cy'] * scale, score=1.0) for t in truth]
            kept, dropped = deduplicate(perfect)
            stress.append(dict(scale=scale, input_distinct_tags=len(perfect),
                               retained=len(kept), incorrectly_merged=dropped,
                               scope='Coordinate-only perfect-read stress test; not a fresh OCR run'))
        rows.append(dict(file=item['file'], family=item['family'],
                         before=score(truth, original, radius),
                         candidate=score(truth, candidate, radius),
                         by_class=by_class, removed=removed, stress=stress))
    result = dict(status='Same-agent development review; no production promotion',
                  inventory_sha256=hashlib.sha256((directory / 'tag-inventory.json').read_bytes()).hexdigest(),
                  evidence_sha256=hashlib.sha256((directory / 'evidence.json').read_bytes()).hexdigest(),
                  matching_policy=inventory['matching_policy'], images=rows)
    with (directory / 'review-metrics.json').open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    for row in rows:
        print(row['file'], row['before'], '->', row['candidate'])
        print('distinct-tag losses at scales 1/.75/.5:', [len(s['incorrectly_merged']) for s in row['stress']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    run(parser.parse_args().directory)
