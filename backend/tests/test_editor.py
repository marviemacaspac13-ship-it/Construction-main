from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.takeoff.contracts import EstimateInputSnapshot, EstimateCorrections, snapshot_catalog
from app.takeoff.corrections import recalculate
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import PlanSchema, FixtureCount

client=TestClient(app)


@pytest.fixture
def setup(catalog,monkeypatch):
    monkeypatch.setenv('ESTIMATE_REVISIONS_ENABLED','true')
    original=EstimateInputSnapshot(plan=PlanSchema(plan_type='Electrical Plan',source='detection',fixtures=[FixtureCount(item_id='OT01',count=12)]),
        params=EstimatingParams(),prices=snapshot_catalog(catalog,'2026-10-11T00:00:00Z'))
    payload={'project_id':str(uuid4()),'scan_revision_id':str(uuid4()),'corrections':{'quantities':{'electrical_counts':{'OT01':3}},'unit_prices':{'OT01':0}},
        'precondition':{'expected_active_revision_id':str(uuid4()),'idempotency_key':str(uuid4())}}
    return original,payload


def test_save_uses_owned_source_and_server_computed_result(setup):
    original,payload=setup
    with patch('app.editor.rpc',side_effect=[{'original_input':original.model_dump(mode='json')},'saved']) as rpc:
        response=client.post('/api/estimate/editor/revisions',json=payload)
    assert response.status_code==200,response.text
    assert rpc.call_args_list[0].args[0]=='owned_estimate_scan'
    assert rpc.call_args_list[0].args[1]['p_owner']=='test-user'
    saved=rpc.call_args_list[1].args[1]
    assert saved['p_scan_id']==payload['scan_revision_id']
    line=next(li for li in saved['p_estimate']['line_items'] if li['item_id']=='OT01')
    assert line['quantity']==3 and line['unit_price']==0
    assert original.plan.fixtures[0].count==12


@pytest.mark.parametrize('field',['estimate','original_input','created_by'])
def test_client_cannot_supply_trusted_data(setup,field):
    _,payload=setup
    payload[field]={}
    with patch('app.editor.rpc') as rpc:
        assert client.post('/api/estimate/editor/revisions',json=payload).status_code==422
    rpc.assert_not_called()


def test_owner_refusal_stops_before_computation(setup):
    _,payload=setup
    with patch('app.editor.rpc',side_effect=HTTPException(404,'Project not found.')) as rpc:
        assert client.post('/api/estimate/editor/revisions',json=payload).status_code==404
    assert rpc.call_count==1


def test_conflict_preserves_original_and_is_returned_to_editor(setup):
    original,payload=setup
    with patch('app.editor.rpc',side_effect=[{'original_input':original.model_dump(mode='json')},HTTPException(409,'Revision changed')]):
        assert client.post('/api/estimate/editor/revisions',json=payload).status_code==409


@pytest.mark.parametrize('trade,counts',[('Electrical Plan',{'electrical_counts':{'OT01':0}}),('Plumbing Plan',{'plumbing_counts':{'water_closet':1}})])
def test_explicit_manual_counts_can_be_below_auto_floor(setup,catalog,trade,counts):
    _,p=setup
    payload={'project_id':p['project_id'],'asset_id':str(uuid4()),'inputs':{'quantities':counts,'confirmed':True}}
    context={'plan_type':trade,'asset':{'source_sha256':'a'*64,'storage_path':'private/plan.png'}}
    with patch('app.editor.rpc',return_value=context),patch('app.editor.load_catalog',return_value=catalog):
        r=client.post('/api/estimate/manual/preview',json=payload)
    assert r.status_code==200,r.text
    assert r.json()['effective_input']['plan']['source']=='manual'
    assert r.json()['effective_input']['plan']['fixture_tags']==counts.get('plumbing_counts',{})


def test_manual_unknown_not_treated_as_zero(setup,catalog):
    _,p=setup
    payload={'project_id':p['project_id'],'asset_id':str(uuid4()),'inputs':{'quantities':{},'confirmed':True}}
    with patch('app.editor.rpc',return_value={'plan_type':'Floor Plan','asset':{'storage_path':'private/original.png'}}):
        assert client.post('/api/estimate/manual/preview',json=payload).status_code==422


def test_manual_zero_geometry_can_be_corrected_later_and_save_retries_stable(setup,catalog):
    _,p=setup
    asset={'source_sha256':'a'*64,'original_filename':'plan.png','media_type':'image/png','byte_size':123,'storage_path':'private/original.png'}
    payload={'project_id':p['project_id'],'asset_id':str(uuid4()),'inputs':{'quantities':{'wall_height_m':2.7,'column_count':0,'slab_area_m2':0},
        'width_m':10,'length_m':12,'exterior_wall_m':44,'interior_wall_m':20,'doors':4,'windows':5,'confirmed':True}}
    context={'plan_type':'Floor Plan','asset':asset}
    with patch('app.editor.rpc',return_value=context),patch('app.editor.load_catalog',return_value=catalog):
        r=client.post('/api/estimate/manual/preview',json=payload)
    assert r.status_code==200,r.text
    source=EstimateInputSnapshot.model_validate(r.json()['effective_input'])
    corrected=recalculate(source,EstimateCorrections(quantities={'column_count':12,'slab_area_m2':80}))
    assert next(e.count for e in corrected.effective_input.plan.concrete if e.kind=='column')==12
    payload.update(prices=r.json()['effective_input']['prices'],precondition=p['precondition'])
    requests=[]
    for _ in range(2):
        with patch('app.editor.rpc',side_effect=[context,'saved']) as rpc:
            result=client.post('/api/estimate/manual/revisions',json=payload)
        assert result.status_code==200,result.text
        requests.append(rpc.call_args.args[1])
    assert requests[0]==requests[1]
    assert requests[0]['p_result']['scan']['method']=='manual'
    assert requests[0]['p_asset']['asset_id']==payload['asset_id']
