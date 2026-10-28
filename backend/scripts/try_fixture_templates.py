"""Bounded same-sheet fixture trial; candidate output only, never priced.

Run from repository root with backend/.venv/Scripts/python.exe.
Uses the first existing draft box per class as a simulated user selection.
No training, OCR, threshold sweep, or changes to production matching.
"""
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

import cv2
import numpy as np
from PIL import Image, ImageDraw

PILOT = Path(__file__).resolve().parents[1] / 'datasets/plumbing-pilot'
sys.path.insert(0, str(PILOT))
from benchmark import iou, match

OUT = PILOT.parent / 'assisted-template-trial-2026-10-16'
POLICY = dict(threshold=0.60, scales=[0.8, 0.9, 1.0, 1.1, 1.2],
              rotations=[0, 90, 180, 270], mirrors=True, suppression_iou=0.3,
              seed_selection='first existing draft annotation per class; simulated user input',
              automatic_acceptance=False)


def propose(gray, seeds):
    """Return review candidates using only the image and selected seed boxes."""
    candidates = []
    height, width = gray.shape
    for seed in seeds:
        x, y, w, h = seed['bbox']
        if min(w, h) < 3 or min(x, y) < 0 or x+w > width or y+h > height:
            raise ValueError('Selected fixture must be inside the image and at least 3px wide/high.')
        base = gray[y:y+h, x:x+w]
        if base.std() < 1:
            raise ValueError('Selected region has no usable shape contrast.')
        for mirror in (False, True):
            for turn in range(4):
                rotated = np.rot90(np.fliplr(base) if mirror else base, turn).copy()
                for scale in POLICY['scales']:
                    template = cv2.resize(rotated, None, fx=scale, fy=scale)
                    th, tw = template.shape
                    if th > height or tw > width:
                        continue
                    scores = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                    maxima = (scores >= POLICY['threshold']) & (scores >= cv2.dilate(scores, np.ones((3, 3), np.uint8)))
                    for yy, xx in zip(*np.where(maxima)):
                        candidates.append(dict(class_id=seed['class_id'], bbox=[int(xx), int(yy), tw, th],
                                               score=float(scores[yy, xx])))
    kept = []
    for candidate in sorted(candidates, key=lambda p: -p['score']):
        if not any(iou(candidate['bbox'], p['bbox']) > POLICY['suppression_iou'] for p in kept):
            kept.append(candidate)
    return kept


def main():
    OUT.mkdir(exist_ok=False)  # Preserve earlier results rather than overwriting them.
    (OUT/'policy.json').write_text(json.dumps(POLICY, indent=2))
    coco = json.loads((PILOT/'annotations.coco.json').read_text())
    reports = []
    for info in coco['images']:
        annotations = [a for a in coco['annotations'] if a['image_id'] == info['id']]
        selected = [next(a for a in annotations if a['category_id'] == c) for c in (0, 1)]
        seeds = [dict(class_id=a['category_id'], bbox=a['bbox']) for a in selected]
        path = PILOT/'images'/info['file_name']
        start = perf_counter()
        gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        predictions = propose(gray, seeds)
        runtime_ms = (perf_counter()-start)*1000
        truth = [dict(class_id=a['category_id'], bbox=a['bbox']) for a in annotations]
        novel_truth = [dict(class_id=a['category_id'], bbox=a['bbox']) for a in annotations if a not in selected]
        novel_predictions = [p for p in predictions if not any(iou(p['bbox'], s['bbox']) >= .3 for s in seeds)]
        metrics = {}
        for threshold in (.5, .3):
            pairs = match(truth, predictions, threshold)
            novel_pairs = match(novel_truth, novel_predictions, threshold)
            metrics[str(threshold)] = dict(correct=len(pairs), false=len(predictions)-len(pairs),
                missed=len(truth)-len(pairs), discovery=len(novel_pairs), discoverable=len(novel_truth))
        matched = {j for _, j in match(truth, predictions, .5)}
        overlay = Image.open(path).convert('RGB').resize((gray.shape[1]*2, gray.shape[0]*2))
        draw = ImageDraw.Draw(overlay)
        for j, p in enumerate(predictions):
            x, y, w, h = p['bbox']
            color = '#d62828' if p['class_id'] == 0 else '#0055dd'
            draw.rectangle((x*2, y*2, (x+w)*2, (y+h)*2), outline=color, width=2)
            draw.text((x*2, max(0, y*2-12)), f"{j+1}: {'WC' if p['class_id']==0 else 'LAV'}" + (' !' if j not in matched else ''), fill=color)
        overlay.save(OUT/f"{Path(info['file_name']).stem}-review.png")
        reports.append(dict(file=info['file_name'], sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            seed_ids=[a['id'] for a in selected], seeds=seeds, runtime_ms=runtime_ms,
            metrics=metrics, predictions=predictions))
    (OUT/'results.json').write_text(json.dumps(reports, indent=2))
    print(json.dumps([{k:r[k] for k in ('file', 'runtime_ms', 'metrics')} for r in reports], indent=2))


if __name__ == '__main__':
    main()
