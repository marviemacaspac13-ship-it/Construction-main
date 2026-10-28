"""Frozen offline canonical-tag polygon-overlap probe. Never changes counting.

Policy v1: same canonical class, convex quadrilateral IoU >= 0.5, highest OCR
confidence retained. No distance fallback without valid geometry. Apply only to
the existing accepted tag observations; upstream exact-string merging remains.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

POLICY = {'version': 1, 'minimum_iou': 0.5, 'same_canonical_class': True,
          'missing_geometry': 'keep', 'ranking': 'descending OCR confidence',
          'scope': 'offline post-count observation probe; upstream merging unchanged'}


def polygon(quad):
    if quad is None:
        return None
    points = np.asarray(quad, dtype=np.float32)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        return None
    hull = cv2.convexHull(points)
    return hull if cv2.contourArea(hull) > 0 else None


def overlap(a, b):
    first, second = polygon(a.get('quad')), polygon(b.get('quad'))
    if first is None or second is None:
        return 0.0
    intersection, _ = cv2.intersectConvexConvex(first, second)
    union = cv2.contourArea(first) + cv2.contourArea(second) - intersection
    return float(intersection / union) if union > 0 else 0.0


def deduplicate(observations):
    kept, removed = [], []
    for item in sorted(observations, key=lambda o: -o['score']):
        duplicate = next((k for k in kept if k['tag'] == item['tag']
                          and overlap(k, item) >= POLICY['minimum_iou']), None)
        if duplicate is None:
            kept.append(item)
        else:
            removed.append(dict(id=item['id'], retained_id=duplicate['id'],
                                tag=item['tag'], iou=overlap(duplicate, item)))
    return kept, removed


def run(directory):
    source = directory / 'evidence.json'
    comparisons = []
    for row in json.loads(source.read_text()):
        kept, removed = deduplicate(row['observations'])
        comparisons.append(dict(file=row['file'], pixel_sha256=row['pixel_sha256'],
                                before=row['before_counts'],
                                candidate=dict(Counter(o['tag'] for o in kept)),
                                removed=removed,
                                geometry_available=sum(polygon(o.get('quad')) is not None
                                                       for o in row['observations'])))
    result = dict(policy=POLICY, evidence_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  comparisons=comparisons)
    with (directory / 'geometry-probe.json').open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    run(parser.parse_args().directory)
