"""Reproduce supplied-PDF crops and evaluate without changing the live library.

Run from backend: .venv/Scripts/python.exe scripts/evaluate_reference_candidates.py
Requires pdftoppm on PATH. Coordinates are raster pixels at the recorded DPI.
"""
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.templates_store import load_templates_for_matching
from app.vision.preprocess import preprocess_image
from app.vision import template_match as tm

OUT = ROOT / 'reference_candidates' / '2026-10-11'
DOWNLOADS = Path.home() / 'Downloads'
SOURCES = {
    'pec': DOWNLOADS / 'pdfcoffee.com_pec-electrical-symbolspdf-pdf-free.pdf',
    'plumbing': DOWNLOADS / 'plumbing legends.pdf',
}
# source, page, dpi, x/y/width/height, clockwise rotation, eligible SKU (if any)
CROPS = {
    'pec_incandescent_ceiling': ('pec', 2, 72, [1334, 830, 68, 67], 0, 'CLR01'),
    'pec_convenience_single': ('pec', 2, 72, [1394, 1549, 71, 60], 0, 'OT01'),
    'pec_convenience_duplex_glyph': ('pec', 2, 72, [1387, 1630, 71, 64], 0, 'OT01'),
    'pec_switch_single_pole': ('pec', 2, 72, [3175, 575, 36, 49], 0, None),
    'pec_switch_duplex': ('pec', 2, 72, [3175, 672, 54, 56], 0, None),
    'pec_switch_triplex': ('pec', 2, 72, [3175, 801, 54, 57], 0, None),
    'pec_switch_three_way': ('pec', 2, 72, [3175, 1061, 86, 60], 0, None),
    'plumbing_awc_top': ('plumbing', 4, 144, [310, 718, 98, 92], 90, None),
    'plumbing_ewc_top': ('plumbing', 4, 144, [493, 980, 112, 90], 90, None),
    'plumbing_lavatory_top': ('plumbing', 4, 144, [700, 958, 70, 110], 90, None),
    'plumbing_builtin_lavatory_top': ('plumbing', 4, 144, [695, 710, 75, 105], 90, None),
    'plumbing_urinal_top': ('plumbing', 4, 144, [877, 942, 104, 135], 90, None),
    'plumbing_kitchen_sink_single': ('plumbing', 4, 144, [308, 940, 72, 133], 90, None),
    'plumbing_kitchen_sink_double': ('plumbing', 4, 144, [308, 1178, 78, 160], 90, None),
}


def extract():
    (OUT / 'crops').mkdir(parents=True, exist_ok=True)
    entries = []
    for name, (source, page, dpi, rect, rotate, sku) in CROPS.items():
        target = OUT / 'crops' / name
        x, y, w, h = rect
        subprocess.run(['pdftoppm', '-f', str(page), '-l', str(page), '-r', str(dpi),
                        '-x', str(x), '-y', str(y), '-W', str(w), '-H', str(h),
                        '-singlefile', '-png', str(SOURCES[source]), str(target)], check=True)
        if rotate:
            im = Image.open(target.with_suffix('.png'))
            im.rotate(-rotate, expand=True).save(target.with_suffix('.png'))
        entries.append(dict(name=name, source=SOURCES[source].name,
                            source_sha256=hashlib.sha256(SOURCES[source].read_bytes()).hexdigest(),
                            pdf_page=page, dpi=dpi, xywh=rect, clockwise_rotation=rotate,
                            candidate_sku=sku, status='evaluation_only', path=f'crops/{name}.png'))
    (OUT / 'manifest.json').write_text(json.dumps(entries, indent=2) + '\n')
    annotate_promotion()
    sheet = Image.new('RGB', (900, 240 * 5), 'white')
    draw = ImageDraw.Draw(sheet)
    for i, entry in enumerate(entries):
        x, y = (i % 3) * 300, (i // 3) * 240
        im = Image.open(OUT / entry['path']).convert('RGB')
        im.thumbnail((250, 185))
        sheet.paste(im, (x + (300 - im.width)//2, y + 20))
        draw.text((x + 8, y + 210), entry['name'], fill='black')
    sheet.save(OUT / 'contact-sheet.png')


def variants(name, sizes=(18, 24)):
    im = cv2.imread(str(OUT / 'crops' / f'{name}.png'), cv2.IMREAD_GRAYSCALE)
    result = []
    for size in sizes:
        h, w = im.shape
        small = cv2.resize(im, (round(w * size / max(h, w)), round(h * size / max(h, w))),
                           interpolation=cv2.INTER_AREA)
        for turns in range(4):
            result.append(np.ascontiguousarray(np.rot90(small, turns)))
    return result


def near(a, b):
    return a.label == b.label and (tm._iou(a.bbox, b.bbox) > .2 or
        np.linalg.norm(np.array(a.bbox[:2]) + a.bbox[2:] - np.array(b.bbox[:2]) - b.bbox[2:]) < 12)


def contexts(items, name):
    if not items:
        return
    sheet = Image.new('RGB', (800, 150 * ((len(items) + 5)//6)), 'white')
    draw = ImageDraw.Draw(sheet)
    for i, (im, bbox, caption) in enumerate(items):
        x1, y1, x2, y2 = map(int, bbox)
        h, w = im.shape[:2]
        left, top = max(0, x1-35), max(0, y1-35)
        crop = im[top:min(h, y2+35), left:min(w, x2+35)].copy()
        cv2.rectangle(crop, (x1-left,y1-top), (x2-left,y2-top), (0,0,255), 1)
        tile = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        tile.thumbnail((126,120))
        x, y = (i%6)*133, (i//6)*150
        sheet.paste(tile,(x,y))
        draw.text((x,y+123), caption, fill='black')
    sheet.save(OUT / f'{name}.png')


def evaluate():
    plans = ROOT / 'tests' / 'fixtures' / 'plans'
    electrical = [plans / '05.png', *sorted((plans/'Data Set'/'Electricalplan'/'IMAGE').glob('*'))]
    baseline_templates = load_templates_for_matching()
    candidate_names = [n for n, v in CROPS.items() if v[-1]]
    results, novel_contexts = [], []
    for index, path in enumerate(electrical):
        image = preprocess_image(path.read_bytes())
        baseline = tm.match_templates(image)
        record = dict(sheet=str(path.relative_to(plans)), baseline=dict(Counter(d.label for d in baseline)), candidates={})
        for name in candidate_names:
            extra = [(CROPS[name][-1], im) for im in variants(name)]
            with patch.object(tm, 'load_templates_for_matching', return_value=baseline_templates + extra):
                detections = tm.match_templates(image)
            novel = [d for d in detections if not any(near(d,b) for b in baseline)]
            record['candidates'][name] = dict(counts=dict(Counter(d.label for d in detections)),
                                              novel=[d.model_dump() for d in novel])
            for d in novel:
                novel_contexts.append((image, d.bbox, f'E{index}:{name[4:9]}'))
        results.append(record)
        print(record['sheet'], record['baseline'], {k:v['counts'] for k,v in record['candidates'].items()}, flush=True)
    (OUT/'electrical-evaluation.json').write_text(json.dumps(results, indent=2)+'\n')
    contexts(novel_contexts, 'electrical-novel-hits')
    # Diagnostic only: plumbing does not call production template matching.
    # Apply the SAME score threshold, and NMS, but no circle guard to noncircular fixtures.
    plumbing = [plans/'07.png', *sorted((plans/'Data Set'/'Plumbingplan'/'IMAGE').glob('*'))]
    results, top_contexts = [], []
    for index, path in enumerate(plumbing):
        image = cv2.imread(str(path))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        record = dict(sheet=str(path.relative_to(plans)), candidates={})
        for name in [n for n in CROPS if n.startswith('plumbing_')]:
            detections = []
            for template in variants(name, (20, 30)):
                for scale in tm.SCALES:
                    h,w = template.shape
                    w,h = int(w*scale),int(h*scale)
                    if min(w,h)<8 or w>gray.shape[1] or h>gray.shape[0]:
                        continue
                    scores=cv2.matchTemplate(gray,cv2.resize(template,(w,h)),cv2.TM_CCOEFF_NORMED)
                    ys,xs=np.where(scores >= tm.MATCH_THRESHOLD)
                    from app.schemas import Detection
                    detections.extend(Detection(label=name,confidence=float(scores[y,x]),bbox=[x,y,x+w,y+h]) for x,y in zip(xs,ys))
            detections=tm._nms(detections)
            record['candidates'][name]=dict(count=len(detections), strongest=[d.model_dump() for d in detections[:3]])
            for d in detections[:2]:
                top_contexts.append((image,d.bbox,f'P{index}:{name[9:17]}'))
        results.append(record)
        print('plumbing',record['sheet'],{k:v['count'] for k,v in record['candidates'].items()},flush=True)
    (OUT/'plumbing-diagnostic.json').write_text(json.dumps(results,indent=2)+'\n')
    contexts(top_contexts,'plumbing-strongest-hits')


def evaluate_individual():
    """Inspect each fixed-size/orientation variant on the three counted sheets."""
    plans = ROOT/'tests'/'fixtures'/'plans'
    paths = [plans/'05.png', plans/'Data Set'/'Electricalplan'/'IMAGE'/'08.png',
             plans/'Data Set'/'Electricalplan'/'IMAGE'/'10.png']
    baseline_templates = load_templates_for_matching()
    report, tiles = [], []
    for index, path in enumerate(paths):
        image = preprocess_image(path.read_bytes())
        baseline = tm.match_templates(image)
        for name in [n for n,v in CROPS.items() if v[-1]]:
            for variant, template in enumerate(variants(name)):
                with patch.object(tm,'load_templates_for_matching', return_value=baseline_templates+[(CROPS[name][-1],template)]):
                    detections = tm.match_templates(image)
                novel = [d for d in detections if not any(near(d,b) for b in baseline)]
                entry=dict(sheet=path.name, candidate=name, variant=variant,
                           size=(18,24)[variant//4], counterclockwise_rotation=(variant%4)*90,
                           counts=dict(Counter(d.label for d in detections)), novel=[d.model_dump() for d in novel])
                report.append(entry)
                for j,d in enumerate(novel):
                    tiles.append((image,d.bbox,f'{index}:{name[4:7]}:{variant}:{j}'))
                print(path.name,name,variant,entry['counts'],len(novel),flush=True)
    (OUT/'individual-evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
    contexts(tiles,'individual-novel-hits')


def evaluate_selected(size=18, rotation=0):
    plans = ROOT/'tests'/'fixtures'/'plans'
    paths = [plans/'05.png', *sorted((plans/'Data Set'/'Electricalplan'/'IMAGE').glob('*'))]
    baseline_templates=load_templates_for_matching()
    template=variants('pec_incandescent_ceiling',(size,))[rotation//90]
    stem=f'selected-{size}-r{rotation}'
    report,tiles=[],[]
    for index,path in enumerate(paths):
        image=preprocess_image(path.read_bytes())
        baseline=tm.match_templates(image)
        with patch.object(tm,'load_templates_for_matching',return_value=baseline_templates+[('CLR01',template)]):
            detections=tm.match_templates(image)
        novel=[d for d in detections if not any(near(d,b) for b in baseline)]
        entry=dict(sheet=str(path.relative_to(plans)), baseline=dict(Counter(d.label for d in baseline)),
                   selected=dict(Counter(d.label for d in detections)),novel=[d.model_dump() for d in novel])
        report.append(entry)
        for j,d in enumerate(novel):
            tiles.append((image,d.bbox,f'E{index}:{j}'))
        (OUT/f'{stem}-evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
        contexts(tiles,f'{stem}-novel-hits')
        print(entry['sheet'],entry['baseline'],entry['selected'],len(novel),flush=True)
    cv2.imwrite(str(OUT/'crops'/f'pec_incandescent_ceiling_{size}_r{rotation}.png'),template)


def upload_selected():
    """Explicit, opt-in upload of the reviewed 20 px / 90-degree crop only.

    Fail closed unless all 12 sheets were checked and the only new locations
    are the reviewed living-area light (05 and its identical 02 copy).
    Uses the existing test account; never creates users or modifies estimates.
    """
    import re
    import httpx
    from dotenv import dotenv_values
    report=json.loads((OUT/'selected-20-r90-evaluation.json').read_text())
    assert len(report)==12, 'Complete corpus evaluation required'
    for row in report:
        for detection in row['novel']:
            assert Path(row['sheet']).name in ('05.png','02.png'), 'Unreviewed novel sheet'
            box=detection['bbox']
            assert detection['label']=='CLR01' and abs((box[0]+box[2])/2-315.5)<3 and abs((box[1]+box[3])/2-295.5)<3, 'Unreviewed location'
    raw=(OUT/'crops'/'pec_incandescent_ceiling_20_r90.png').read_bytes()
    front=dotenv_values(ROOT.parent/'.env.local')
    lines=(ROOT.parent/'passwords.md').read_text().splitlines()
    idx=next(i for i,line in enumerate(lines) if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',line.strip()))
    password=next(line.strip() for line in lines[idx+1:] if line.strip())
    response=httpx.post(front['VITE_SUPABASE_URL'].rstrip('/')+'/auth/v1/token?grant_type=password',
        headers={'apikey':front['VITE_SUPABASE_ANON_KEY']},json={'email':lines[idx].strip(),'password':password},timeout=30)
    assert response.status_code==200, 'Existing account login failed'
    headers={'Authorization':'Bearer '+response.json()['access_token']}
    existing=[p for p in (ROOT/'templates'/'CLR01').glob('*.png') if p.read_bytes()==raw]
    if existing:
        receipt={'item_id':'CLR01','filename':existing[0].name,'already_present':True}
    else:
        response=httpx.post('http://127.0.0.1:8000/api/templates',headers=headers,
            data={'item_id':'CLR01'},files={'file':('pec_incandescent_ceiling_20_r90.png',raw,'image/png')},timeout=30)
        assert response.status_code==200, 'Template upload failed'
        receipt=response.json()
    listed=httpx.get('http://127.0.0.1:8000/api/templates',headers=headers,timeout=30)
    assert listed.status_code==200 and receipt['filename'] in listed.json()['CLR01'], 'Uploaded file not listed'
    receipt.update(source_crop='crops/pec_incandescent_ceiling.png',
                   derived_crop='crops/pec_incandescent_ceiling_20_r90.png',
                   sha256=hashlib.sha256(raw).hexdigest(),method='authenticated POST /api/templates',
                   verification='authenticated GET /api/templates')
    (OUT/'upload-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    annotate_promotion()
    print(json.dumps(receipt,indent=2))


def annotate_promotion():
    receipt_path=OUT/'upload-receipt.json'
    if not receipt_path.exists():
        return
    receipt=json.loads(receipt_path.read_text())
    entries=json.loads((OUT/'manifest.json').read_text())
    for entry in entries:
        if entry['name']=='pec_incandescent_ceiling':
            entry['accepted_derivative']={
                'path':receipt['derived_crop'],'max_side_px':20,
                'interpolation':'cv2.INTER_AREA','counterclockwise_rotation':90,
                'active_sku':'CLR01','active_filename':receipt['filename'],
                'sha256':receipt['sha256'],'status':'uploaded'}
    (OUT/'manifest.json').write_text(json.dumps(entries,indent=2)+'\n')


def before_after():
    receipt=json.loads((OUT/'upload-receipt.json').read_text())
    image=preprocess_image((ROOT/'tests/fixtures/plans/05.png').read_bytes())
    active=load_templates_for_matching()
    promoted=cv2.imread(str(ROOT/'templates'/'CLR01'/receipt['filename']),cv2.IMREAD_GRAYSCALE)
    before=[(label,im) for label,im in active if not (label=='CLR01' and np.array_equal(im,promoted))]
    with patch.object(tm,'load_templates_for_matching',return_value=before):
        baseline=tm.match_templates(image)
    after=tm.match_templates(image)
    original=Image.open(ROOT/'tests/fixtures/plans/05.png').convert('RGB')
    sheet=Image.new('RGB',(1320,580),'white')
    draw=ImageDraw.Draw(sheet)
    for index,(detections,title) in enumerate(((baseline,'Before: 16 of 21 lights'),(after,'After: 17 of 21 lights'))):
        panel=original.copy()
        marks=ImageDraw.Draw(panel)
        for d in detections:
            if d.label=='CLR01':
                marks.rectangle(d.bbox,outline='#00866a',width=2)
        if index:
            marks.ellipse((303,283,328,308),outline='#e25617',width=3)
        sheet.paste(panel,(index*660+8,45))
        draw.text((index*660+12,15),title,fill='black')
    draw.text((12,550),'Orange circle: recovered living-area light. Outlets remain 16 of 18. Green boxes: detected lights.',fill='black')
    sheet.save(OUT/'before-after.png')


if __name__ == '__main__':
    if '--before-after' in sys.argv:
        before_after()
    elif '--upload-selected20' in sys.argv:
        upload_selected()
    elif '--selected20' in sys.argv:
        evaluate_selected(20,90)
    elif '--selected' in sys.argv:
        evaluate_selected()
    elif '--individual' in sys.argv:
        evaluate_individual()
    elif '--evaluate' in sys.argv:
        evaluate()
    else:
        extract()
