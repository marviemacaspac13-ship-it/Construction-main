"""Replay six frozen OCR reads through the cleanout fix and pricing guard."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import main
from app.extract.ocr import TextBox
from app.extract.tags import count_tags, tally
from app.takeoff.constants import FIXTURE_TAG_PATTERNS
from app.takeoff.estimator import estimate_plan
from app.takeoff.schema import PlanSchema
from scripts.score_tag_review import score


def run(output):
    evidence_path = ROOT/'datasets/tag-geometry-stage1/evidence.json'
    inventory_path = ROOT/'datasets/tag-evidence-stage1/tag-inventory.json'
    evidence = json.loads(evidence_path.read_text())
    inventory = json.loads(inventory_path.read_text())
    catalog_rows = json.loads((ROOT/'tests/fixtures/catalog.json').read_text())
    catalog = {r['item_id']: r for r in catalog_rows}
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for row in evidence:
        raw = (ROOT/'datasets'/row['source']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row['sha256']
        boxes = [TextBox(**b) for b in row['ocr_boxes']]
        counts = count_tags(boxes, FIXTURE_TAG_PATTERNS, (row['height'],row['width'],3))
        after = dict(tally(counts))
        observations = [dict(tag=tag, **asdict(b)) for tag, value in counts.items() for b in value.boxes]
        status = 'accepted'
        plan = None
        with patch.object(main, 'read_tiled', return_value=boxes):
            try:
                plan, _ = main._read_plumbing(raw, 'Plumbing Plan')
                assert plan.fixture_tags == after
                assert len(plan.fixture_tag_observations) == len(observations)
            except main.HTTPException as exc:
                assert exc.status_code == 422
                status = 'refused'
        assert status == row['status']
        assert {k:v for k,v in after.items() if k!='cleanout'} == {
            k:v for k,v in row['before_counts'].items() if k!='cleanout'}
        pricing = None
        if plan is not None:
            original = PlanSchema(plan_type='Plumbing Plan', source='tags', fixture_tags=row['before_counts'])
            before_estimate = estimate_plan(original, catalog)
            after_estimate = estimate_plan(plan, catalog)
            assert before_estimate.grand_total == after_estimate.grand_total
            assert [i.model_dump() for i in before_estimate.line_items] == [i.model_dump() for i in after_estimate.line_items]
            pricing = dict(before=before_estimate.grand_total, after=after_estimate.grand_total,
                           catalog='committed offline fixture snapshot', line_items_unchanged=True)
        truth = next(r['annotations'] for r in inventory['images'] if r['file']==row['file'])
        results.append(dict(file=row['file'], family=row['family'], before=row['before_counts'],
                            after=after, route_before=row['status'], route_after=status,
                            before_metrics=score(truth,row['observations'],8),
                            after_metrics=score(truth,observations,8), observations=observations,
                            pricing=pricing))
    report = dict(scope='Replay of frozen real-image OCR, not a new OCR run; same-agent development inventory',
                  source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in [evidence_path, inventory_path, ROOT/'app/extract/tags.py',Path(__file__)]},
                  results=results)
    (output/'comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    for r in results:
        print(r['file'], r['before'], '->', r['after'], r['route_after'],r['pricing'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
