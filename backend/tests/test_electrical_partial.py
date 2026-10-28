"""Partial scope never invokes wiring rules; review survives pricing and storage."""
from copy import deepcopy
import io
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app import electrical_review as boundary
from app.electrical_models import ElectricalChoice, ElectricalObservation, assess
from app.main import app
from app.schemas import Detection
from app.takeoff.contracts import EstimateCorrections, EstimateInputSnapshot, snapshot_catalog
from app.takeoff.corrections import recalculate
from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import PlanSchema


@pytest.fixture
def raw():
    buf=io.BytesIO();Image.new('RGB',(100,80),'white').save(buf,'PNG');return buf.getvalue()


def choice(id='a', cls='switch', sku='SW02', **changes):
    obs=ElectricalObservation(id=id,assembly_id=id,box_2d=[10,10,20,20],device_class=cls,
        gang_count=2 if cls=='switch' else None,switching_function='one_way' if cls=='switch' else None)
    return ElectricalChoice.model_validate(dict(observation=obs.model_dump(),selected_sku=sku,
        box_item_id='UTB01',box_compatibility_confirmed=True,**changes))


def submission(raw, choices):
    return dict(receipt=boundary.issue_review(raw,'test-user',[c.observation for c in choices],
        provider='template',model='offline'),confirmed=True,estimate_scope='devices_and_boxes',
        choices=[c.model_dump(mode='json') for c in choices])


def reviewed(raw, choices):
    return boundary.reviewed_plan(boundary.confirm_review(submission(raw,choices),raw,'test-user'))


def test_two_gang_switch_is_one_set_one_box_without_wire(raw,catalog):
    plan=reviewed(raw,[choice()])
    with patch('app.takeoff.estimator.rules_for',side_effect=AssertionError('legacy wiring invoked')):
        result=estimate_plan(plan,catalog)
    assert {li.item_id:li.quantity for li in result.line_items}=={'SW02':1,'UTB01':1}
    assert result.grand_total==184
    assert result.estimate_scope=='devices_and_boxes'
    assert 'circuit design' in result.scope_exclusions[0]
    assert all(li.rule.startswith('electrical_review_v1.') for li in result.line_items)


@pytest.mark.parametrize('function,sku',[('three_way','SW03'),('four_way','SW02'),('one_way','GS02'),('one_way','SW01')])
def test_switch_function_gang_and_product_cannot_be_conflated(raw,function,sku):
    c=choice().model_dump();c['selected_sku']=sku;c['observation']['switching_function']=function
    c=ElectricalChoice.model_validate(c)
    assert assess(c,partial=True).state=='unresolved'
    with pytest.raises(ValueError,match='Resolve or explicitly exclude'):reviewed(raw,[c])


def test_AC_is_device_only_and_does_not_gain_circuit_allowance(raw,catalog):
    result=estimate_plan(reviewed(raw,[choice(cls='ac_outlet',sku='ACO01')]),catalog)
    assert {li.item_id for li in result.line_items}=={'ACO01','UTB01'}
    assert result.grand_total==71


@pytest.mark.parametrize('changes',[
    {'box_compatibility_confirmed':False},
    {'box_item_id':None,'box_compatibility_confirmed':False},
    {'box_exclusion_reason':'unknown fit'},
    {'selected_sku':None},
])
def test_unconfirmed_box_and_implicit_product_block_partial(raw,changes):
    c=ElectricalChoice.model_validate({**choice().model_dump(),**changes})
    with pytest.raises(ValueError):reviewed(raw,[c])


def test_explicit_box_and_device_exclusions_survive_total_and_replay(raw,catalog):
    outlet=ElectricalChoice.model_validate({**choice(cls='convenience_outlet',sku='OT01').model_dump(),
        'box_item_id':None,'box_compatibility_confirmed':False,'box_exclusion_reason':'Box dimensions unavailable'})
    switch=choice('b');switch.observation.box_2d=(30.,30.,40.,40.)
    switch=ElectricalChoice(observation=switch.observation,disposition='exclude',exclusion_reason='Three-way product unavailable')
    plan=reviewed(raw,[outlet,switch]);result=estimate_plan(plan,catalog)
    assert {li.item_id for li in result.line_items}=={'OT01'}
    assert len(result.scope_exclusions)==3
    snap=EstimateInputSnapshot(plan=plan,params=EstimatingParams(),prices=snapshot_catalog(catalog,result.priced_at))
    snap=EstimateInputSnapshot.model_validate_json(snap.model_dump_json())
    changed=recalculate(snap,EstimateCorrections(unit_prices={'OT01':100})).estimate
    assert changed.grand_total==100 and changed.scope_exclusions==result.scope_exclusions
    assert recalculate(snap,EstimateCorrections()).estimate.grand_total==result.grand_total
    with pytest.raises(ValueError):recalculate(snap,EstimateCorrections(quantities={'electrical_counts':{'OT01':2}}))
    with pytest.raises(ValueError):PlanSchema.model_validate({**plan.model_dump(),'runs':[dict(id='x',length_m=10,service='lighting')]})


def test_endpoint_confirms_exact_image_and_saves_partial_without_detection_recount(raw,catalog,monkeypatch):
    client=TestClient(app);body=submission(raw,[choice()])
    with patch('app.main._detect_plan',side_effect=AssertionError('recount')),patch('app.main.load_catalog',return_value=catalog):
        r=client.post('/api/estimate/image',files={'file':('test.png',raw,'image/png')},
            data={'plan_type':'Electrical Plan','electrical_review':__import__('json').dumps(body)})
    assert r.status_code==200,r.text
    result=r.json();assert result['estimate']['estimate_scope']=='devices_and_boxes'
    monkeypatch.setenv('ESTIMATE_REVISIONS_ENABLED','true')
    payload=dict(project_id=str(uuid4()),precondition=dict(expected_active_revision_id=None,idempotency_key=str(uuid4())),
        result=result,asset=dict(source_sha256=result['scan']['source_sha256'],original_filename='test.png',media_type='image/png',byte_size=len(raw)))
    with patch('app.revisions.rpc',return_value=str(uuid4())) as rpc:
        r=client.post('/api/estimate/revisions',json=payload);assert r.status_code==200,r.text
        assert rpc.call_args.args[1]['p_result']['estimate']['estimate_scope']=='devices_and_boxes'
    tampered=deepcopy(payload);tampered['result']['estimate'].pop('estimate_scope')
    with patch('app.revisions.rpc') as rpc:
        assert client.post('/api/estimate/revisions',json=tampered).status_code==422
        rpc.assert_not_called()


def test_proposals_are_local_normalized_and_do_not_price_sparse_matches(raw):
    with patch('app.main.match_templates',return_value=[Detection(label='OT01',confidence=.9,bbox=[10,8,20,16])]):
        r=TestClient(app).post('/api/electrical/proposals',files={'file':('test.png',raw,'image/png')})
    assert r.status_code==200,r.text
    p=r.json();assert p['proposed'][0]['box_2d']==[100,100,200,200]
    assert 'selected_sku' not in p['proposed'][0] and 'estimate' not in p
    assert p['receipt']


def test_legacy_electrical_output_keeps_existing_allowances(catalog):
    plan=PlanSchema(plan_type='Electrical Plan',fixtures=[dict(item_id='OT01',count=1)])
    result=estimate_plan(plan,catalog)
    assert 'ELW04' in {li.item_id for li in result.line_items}
    assert 'estimate_scope' not in result.model_dump()
