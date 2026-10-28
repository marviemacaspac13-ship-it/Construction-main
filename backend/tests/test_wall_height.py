"""Project-wide image input changes walls without changing the structural frame."""
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.takeoff.contracts import EstimateInputSnapshot
from app.takeoff.estimator import estimate_plan
from app.takeoff.frame import derive_frame
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.structural import compute
from app.takeoff.schema import Opening, PlanSchema, Wall

client = TestClient(app)
PNG = (Path(__file__).parent / 'fixtures' / 'plans' / '01.png').read_bytes()


def scan(plan, catalog, height=None):
    with patch('app.main._read_plan', return_value=(plan, None)), patch('app.main.load_catalog', return_value=catalog):
        return client.post('/api/estimate/image', files={'file': ('plan.png', PNG, 'image/png')},
                           data={'plan_type': 'Floor Plan', **({'wall_height_m': str(height)} if height is not None else {})})


def test_height_changes_wall_materials_and_preserves_frame_and_replay(catalog, monkeypatch):
    plan = PlanSchema(plan_type='Floor Plan', source='ocr',
        walls=[Wall(id='outside', length_m=44, thickness='6in', openings=[Opening(kind='window', width_m=1.2, height_m=1.2, count=4)]),
               Wall(id='inside', length_m=30, thickness='4in')],
        concrete=derive_frame(10, 12, EstimatingParams(), 12).elements)
    low_response, high_response = scan(plan, catalog), scan(plan, catalog, 3.2)
    assert low_response.status_code == high_response.status_code == 200
    low, high = low_response.json(), high_response.json()
    first = EstimateInputSnapshot.model_validate(low['original_input'])
    second = EstimateInputSnapshot.model_validate(high['original_input'])
    assert first.params.default_wall_height_m == 2.7
    assert second.params.default_wall_height_m == 3.2
    assert first.plan == second.plan  # source geometry, openings and structural sections unchanged
    low_bom, high_bom = compute(first.plan, first.params), compute(second.plan, second.params)
    wall_rules = {'structural.chb_blocks', 'structural.laying_mortar', 'structural.rebar', 'structural.tie_wire'}
    for rule in ('structural.chb_blocks', 'structural.laying_mortar', 'structural.rebar'):
        assert sum(x.quantity for x in high_bom if x.rule == rule) > sum(x.quantity for x in low_bom if x.rule == rule)
    assert [x for x in low_bom if x.rule not in wall_rules] == [x for x in high_bom if x.rule not in wall_rules]
    assert high['estimate']['grand_total'] > low['estimate']['grand_total']
    replay = estimate_plan(second.plan, second.prices.to_catalog(), second.params)
    assert replay.model_dump(exclude={'priced_at'}) == {k: v for k, v in high['estimate'].items() if k != 'priced_at'}
    monkeypatch.setenv('ESTIMATE_REVISIONS_ENABLED', 'true')
    payload = {'project_id': str(uuid4()), 'precondition': {'expected_active_revision_id': None, 'idempotency_key': str(uuid4())},
               'result': high, 'asset': {'source_sha256': high['scan']['source_sha256'], 'original_filename': 'plan.png', 'media_type': 'image/png', 'byte_size': 7}}
    with patch('app.revisions._client') as factory:
        factory.return_value.rpc.return_value.execute.return_value = SimpleNamespace(data=str(uuid4()))
        assert client.post('/api/estimate/revisions', json=payload).status_code == 200
    assert factory.return_value.rpc.call_args.args[1]['p_result']['original_input']['params']['default_wall_height_m'] == 3.2


@pytest.mark.parametrize('height', ['0', '-1', '10.01', 'NaN', 'Infinity', '-Infinity', 'abc'])
def test_invalid_height_rejected_before_recognition(height):
    with patch('app.main._read_plan') as reader:
        response = client.post('/api/estimate/image', files={'file': ('plan.png', PNG, 'image/png')},
                               data={'plan_type': 'Floor Plan', 'wall_height_m': height})
    assert response.status_code == 422
    reader.assert_not_called()


@pytest.mark.parametrize('trade', ['Electrical Plan', 'Plumbing Plan'])
def test_nonfloor_height_is_not_silently_ignored(trade):
    response = client.post('/api/estimate/image', files={'file': ('plan.png', PNG, 'image/png')},
                           data={'plan_type': trade, 'wall_height_m': '3'})
    assert response.status_code == 422


def test_maximum_height_accepted(catalog):
    plan = PlanSchema(plan_type='Floor Plan', source='ocr', walls=[Wall(id='w', length_m=8)])
    response = scan(plan, catalog, 10)
    assert response.status_code == 200
    assert response.json()['original_input']['params']['default_wall_height_m'] == 10


@pytest.mark.ocr
def test_fixture_two_heights_and_reset(catalog):
    """Read the real fixture once, then price that exact reading at both heights."""
    from app.main import _read_plan

    raw = (Path(__file__).parent / 'fixtures' / 'plans' / '01.png').read_bytes()
    plan, report = _read_plan(raw, 'Floor Plan')
    assert plan.walls and plan.concrete
    responses = []
    with patch('app.main._read_plan', return_value=(plan, report)), patch('app.main.load_catalog', return_value=catalog):
        for height in (2.7, 3.2, 2.7):
            response = client.post('/api/estimate/image', files={'file': ('01.png', raw, 'image/png')},
                                   data={'plan_type': 'Floor Plan', 'wall_height_m': str(height)})
            assert response.status_code == 200, response.text
            responses.append(response.json())
    low, high, reset = responses
    assert low['original_input']['plan'] == high['original_input']['plan'] == reset['original_input']['plan']
    assert low['estimate']['line_items'] == reset['estimate']['line_items']
    assert low['estimate']['grand_total'] == reset['estimate']['grand_total'] < high['estimate']['grand_total']
    for item_id in ('CHB01', 'CHB02'):
        quantities = [next(x['quantity'] for x in r['estimate']['line_items'] if x['item_id'] == item_id) for r in responses]
        assert quantities[0] == quantities[2] < quantities[1]
    assert low['extraction'] == high['extraction']
