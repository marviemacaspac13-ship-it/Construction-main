"""Frozen offline recognition reread, selected only from OCR outputs.

No labels or known misses enter selection/inference. Scoring happens afterward.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.extract.ocr import TextBox, _engine
from app.extract.tags import count_tags, normalise_tag, tally
from app.takeoff.constants import FIXTURE_TAG_PATTERNS
from scripts.probe_tag_geometry import overlap
from scripts.score_tag_review import score
from scripts.trace_missed_tags import Trace
import re

POLICY = dict(version=1, selection_max_score=.85, max_text_characters=6,
              max_aspect_ratio=6, max_extent_image_fraction=.1, max_regions=100,
              region_merge_iou=.5, existing_tag_exclusion_iou=.3,
              crops=['original_quad', 'axis_bounds_padding_0.25_short_side'],
              acceptance='Both rereads agree on a supported whole token and both scores >= 0.5',
              confidence_cutoff=.5, production_changed=False,
              source='OCR pre-confidence-filter proposals; no ground truth in selection',
              conflicts='Reject overlapping different-class reread proposals')


def canonical(text):
    return next((tag for tag, pat in FIXTURE_TAG_PATTERNS.items()
                 if re.fullmatch(pat, normalise_tag(text), re.I)), None)


def select(proposals, accepted, shape):
    selected = []
    for p in sorted(proposals, key=lambda p: (-p['score'], p['id'])):
        if p['score'] >= POLICY['selection_max_score'] or len(p['text'].strip()) > POLICY['max_text_characters']:
            continue
        quad = np.asarray(p['quad'], np.float32)
        width, height = np.ptp(quad[:,0]), np.ptp(quad[:,1])
        if min(width,height) <= 0 or max(width,height)/min(width,height) > POLICY['max_aspect_ratio']:
            continue
        if max(width,height) > max(shape[:2])*POLICY['max_extent_image_fraction']:
            continue
        if any(overlap(p, b) >= POLICY['existing_tag_exclusion_iou'] for b in accepted):
            continue
        if any(overlap(p, b) >= POLICY['region_merge_iou'] for b in selected):
            continue
        selected.append(p)
        if len(selected) == POLICY['max_regions']:
            break
    return selected


def recognize(image, selected):
    engine = _engine()
    logs, candidates = [], []
    for p in selected:
        quad = np.asarray(p['quad'],np.float32)
        tight = engine.get_crop_img_list(image, [quad])[0]
        width,height = np.ptp(quad[:,0]),np.ptp(quad[:,1])
        pad = .25*min(width,height)
        x0,y0 = np.maximum(0,np.floor(quad.min(axis=0)-pad)).astype(int)
        x1,y1 = np.minimum([image.shape[1],image.shape[0]],np.ceil(quad.max(axis=0)+pad)).astype(int)
        padded = image[y0:y1,x0:x1]
        if padded.shape[0] / padded.shape[1] >= 1.5:
            padded = np.rot90(padded)
        crops = [tight,padded.copy()]
        if engine.use_angle_cls:
            crops,_,_ = engine.text_cls(crops)
        readings,_ = engine.text_recognizer(crops)
        labels = [canonical(text) for text, confidence in readings]
        valid = labels[0] is not None and labels[0] == labels[1] and all(float(s)>=.5 for _,s in readings)
        logs.append(dict(proposal=p, readings=[dict(text=t,score=float(s)) for t,s in readings],
                         agreement=valid, tag=labels[0] if valid else None))
        if valid:
            candidates.append(dict(p, tag=labels[0], text=readings[0][0],
                                   score=min(float(s) for _,s in readings)))
    # Each candidate represents its seed region; reject any type disagreement.
    candidates = [p for p in candidates if not any(p['tag']!=q['tag'] and overlap(p,q)>=.5
                                                    for q in candidates)]
    kept = []
    for p in sorted(candidates,key=lambda p:-p['score']):
        if not any(overlap(p,q)>=.5 for q in kept):
            kept.append(p)
    return kept, logs


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    (output/'policy.json').write_text(json.dumps(dict(POLICY,script_sha256=hashlib.sha256(
        Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n',encoding='utf-8')
    baseline_path=ROOT/'datasets/tag-geometry-stage1/evidence.json'
    baselines=json.loads(baseline_path.read_text())
    results=[]
    for row in baselines:
        start=perf_counter()
        path=ROOT/'datasets'/row['source']
        raw=path.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==row['sha256']
        image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
        if row['file']=='trace-02.png':
            cached=json.loads((ROOT/'datasets/tag-miss-diagnostic/raw-trace.json').read_text())
            proposals=cached['proposals']
            merged=[TextBox(**b) for b in cached['merges'][-1]['output']]
        else:
            trace=Trace(image)
            merged,_,_=trace.run()
            proposals=trace.proposals
        assert json.loads(json.dumps([asdict(b) for b in merged]))==row['ocr_boxes']
        counts=count_tags(merged,FIXTURE_TAG_PATTERNS,image.shape)
        accepted=[dict(tag=t,**asdict(b)) for t,c in counts.items() for b in c.boxes]
        selected=select(proposals,accepted,image.shape)
        candidates,logs=recognize(image,selected)
        # Apply the existing legend filter with all first-pass text as context.
        candidate_boxes=[TextBox(p['text'],p['cx'],p['cy'],p['score'],p['rotated'],p['quad']) for p in candidates]
        filtered=count_tags(merged+candidate_boxes,FIXTURE_TAG_PATTERNS,image.shape)
        after=[dict(tag=t,**asdict(b)) for t,c in filtered.items() for b in c.boxes]
        result=dict(file=row['file'],source=row['source'],source_sha256=row['sha256'],
                    family=row['family'],before=dict(tally(counts)),after=dict(tally(filtered)),
                    before_observations=accepted,after_observations=after,
                    selected_regions=len(selected),readings=logs,raw_proposals=proposals,
                    runtime_seconds=round(perf_counter()-start,3))
        results.append(result)
        (output/'predictions.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
        print(row['file'],len(selected),'regions',result['before'],'->',result['after'],flush=True)
    # Ground-truth coordinates are loaded only after all predictions are frozen.
    inventory_path=ROOT/'datasets/tag-evidence-stage1/tag-inventory.json'
    inventory=json.loads(inventory_path.read_text())
    metrics=[]
    for row in results:
        truth=next(i['annotations'] for i in inventory['images'] if i['file']==row['file'])
        metrics.append(dict(file=row['file'],before=score(truth,row['before_observations'],8),
                            after=score(truth,row['after_observations'],8)))
    (output/'metrics.json').write_text(json.dumps(dict(
        inventory_sha256=hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        scope='Previously exposed same-agent development tags; unsupported and uncertain labels excluded',
        results=metrics),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
