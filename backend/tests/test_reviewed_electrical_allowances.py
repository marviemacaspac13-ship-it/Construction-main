"""Restore established light/outlet allowances without extending switch/AC rules."""
import io
import json
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.electrical_models import ElectricalChoice, ElectricalObservation
from app import electrical_review as boundary
from app.main import app
from app.takeoff.contracts import EstimateCorrections, EstimateInputSnapshot, snapshot_catalog
from app.takeoff.corrections import recalculate
from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import PlanSchema


@pytest.fixture
def raw():
    b=io.BytesIO();Image.new('RGB',(100,100),'white').save(b,'PNG');return b.getvalue()


def choices(skus):
    result=[]
    for i,sku in enumerate(skus):
        kind='light_point' if sku.startswith('CLR') else 'convenience_outlet' if sku.startswith('OT') else 'switch' if sku.startswith('SW') else 'ac_outlet'
        o=ElectricalObservation(id=f'device-{i}',assembly_id=f'assembly-{i}',
            box_2d=[10+i*50,10,20+i*50,20],device_class=kind,
            gang_count=int(sku[-1]) if kind in ('switch','convenience_outlet') else None,
            switching_function='one_way' if kind=='switch' else None)
        result.append(ElectricalChoice(observation=o,selected_sku=sku,
            box_item_id='JCB01' if kind=='light_point' else 'UTB01',box_compatibility_confirmed=True))
    return result


def submission(raw, records, scope='reviewed_device_allowances'):
    return dict(receipt=boundary.issue_review(raw,'test-user',[c.observation for c in records],provider='template',model='offline'),
        confirmed=True,estimate_scope=scope,choices=[c.model_dump() for c in records])


def plan(raw, records, scope='reviewed_device_allowances'):
    return boundary.reviewed_plan(boundary.confirm_review(submission(raw,records,scope),raw,'test-user'))


def allowances(estimate):
    return {li.item_id:li.quantity for li in estimate.line_items if '_from_count' in li.rule}


@pytest.mark.parametrize('sku',['CLR01','CLR02','CLR03','OT01','OT02','OT03'])
def test_supported_variants_reuse_original_quantities_without_duplicate_boxes(raw,catalog,sku):
    records=choices([sku]);reviewed=estimate_plan(plan(raw,records),catalog)
    original=estimate_plan(PlanSchema(plan_type='Electrical Plan',fixtures=[dict(item_id=sku,count=1)]),catalog)
    assert allowances(reviewed)==allowances(original)
    assert reviewed.grand_total==original.grand_total
    box='JCB01' if sku.startswith('CLR') else 'UTB01'
    assert next(li.quantity for li in reviewed.line_items if li.item_id==box)==1
    assert reviewed.estimate_scope=='reviewed_device_allowances'
    assert any('not measured routes' in s for s in reviewed.assumptions)
    assert 'switches and AC' in reviewed.scope_exclusions[0]


def test_mixed_inventory_does_not_apply_convenience_wiring_to_switch_or_AC(raw,catalog):
    result=estimate_plan(plan(raw,choices(['CLR01','OT02','SW02','ACO01'])),catalog)
    supported=estimate_plan(PlanSchema(plan_type='Electrical Plan',fixtures=[dict(item_id='CLR01',count=1),dict(item_id='OT02',count=1)]),catalog)
    assert allowances(result)==allowances(supported)
    assert next(li.quantity for li in result.line_items if li.item_id=='SW02')==1
    assert next(li.quantity for li in result.line_items if li.item_id=='ACO01')==1
    assert next(li.quantity for li in result.line_items if li.item_id=='UTB01')==3


@pytest.mark.parametrize('sku',['SW02','ACO01'])
def test_switch_and_AC_alone_remain_device_and_confirmed_box_only(raw,catalog,sku):
    result=estimate_plan(plan(raw,choices([sku])),catalog)
    assert {li.item_id for li in result.line_items}=={sku,'UTB01'}
    assert allowances(result)=={}


def test_explicit_box_omission_does_not_remove_supported_wire_allowance(raw,catalog):
    c=choices(['CLR01'])[0]
    c=ElectricalChoice.model_validate({**c.model_dump(),'box_item_id':None,
        'box_compatibility_confirmed':False,'box_exclusion_reason':'Box dimensions unspecified'})
    result=estimate_plan(plan(raw,[c]),catalog)
    assert 'JCB01' not in {li.item_id for li in result.line_items}
    assert {'ELW05','FPVC01'}<=set(allowances(result))
    assert len(result.scope_exclusions)==2


def test_excluded_devices_add_no_wire_or_boxes(raw,catalog):
    records=choices(['CLR01','OT01'])
    records[0]=ElectricalChoice(observation=records[0].observation,disposition='exclude',exclusion_reason='Legend example')
    result=estimate_plan(plan(raw,records),catalog)
    only_outlet=estimate_plan(PlanSchema(plan_type='Electrical Plan',fixtures=[dict(item_id='OT01',count=1)]),catalog)
    assert allowances(result)==allowances(only_outlet)
    assert 'ELW05' not in {li.item_id for li in result.line_items}


def test_historical_partial_scope_stays_unchanged(raw,catalog):
    p=plan(raw,choices(['CLR01']),'devices_and_boxes')
    restored=PlanSchema.model_validate_json(p.model_dump_json())
    result=estimate_plan(restored,catalog)
    assert {li.item_id for li in result.line_items}=={'CLR01','JCB01'}
    assert result.grand_total==40
    assert result.scope_exclusions[0]=='Wires, conduit, breakers, panels and circuit design are excluded.'


def test_snapshot_price_edit_reset_and_tampered_counts_preserve_new_scope(raw,catalog):
    p=plan(raw,choices(['CLR01','OT01','SW02']))
    before=estimate_plan(p,catalog)
    snap=EstimateInputSnapshot(plan=p,params=EstimatingParams(),prices=snapshot_catalog(catalog,before.priced_at))
    snap=EstimateInputSnapshot.model_validate_json(snap.model_dump_json())
    edited=recalculate(snap,EstimateCorrections(unit_prices={'ELW05':30}))
    assert edited.estimate.estimate_scope=='reviewed_device_allowances'
    assert allowances(edited.estimate)==allowances(before)
    assert edited.effective_input.plan.electrical_review==snap.plan.electrical_review
    reset=recalculate(snap,EstimateCorrections()).estimate
    assert reset.model_dump(exclude={'priced_at'})==before.model_dump(exclude={'priced_at'})
    with pytest.raises(ValueError):recalculate(snap,EstimateCorrections(quantities={'electrical_counts':{'OT01':5}}))


def test_image_endpoint_and_recomputed_revision_save_accept_new_scope(raw,catalog,monkeypatch):
    client=TestClient(app);body=submission(raw,choices(['CLR01','OT01','SW02','ACO01']))
    with patch('app.main._detect_plan',side_effect=AssertionError('must not recount')),patch('app.main.load_catalog',return_value=catalog):
        response=client.post('/api/estimate/image',files={'file':('test.png',raw,'image/png')},
            data={'plan_type':'Electrical Plan','electrical_review':json.dumps(body)})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['estimate']['estimate_scope']=='reviewed_device_allowances'
    assert {'ELW04','ELW05','FPVC01'}<={li['item_id'] for li in data['estimate']['line_items']}
    payload=dict(project_id=str(uuid4()),precondition=dict(expected_active_revision_id=None,idempotency_key=str(uuid4())),
        result=data,asset=dict(source_sha256=data['scan']['source_sha256'],original_filename='test.png',media_type='image/png',byte_size=len(raw)))
    monkeypatch.setenv('ESTIMATE_REVISIONS_ENABLED','true')
    with patch('app.revisions.rpc',return_value=str(uuid4())) as rpc:
        saved=client.post('/api/estimate/revisions',json=payload)
        assert saved.status_code==200,saved.text
        evidence=rpc.call_args.args[1]['p_result']['original_input']['plan']['electrical_review']
        assert evidence['estimate_scope']=='reviewed_device_allowances'


@pytest.mark.parametrize('sku', ['SW01', 'SW02', 'SW03'])
def test_group_confirmed_switch_specs_preserve_unknown_raw_evidence_and_snapshot(raw, catalog, sku):
    original = ElectricalObservation(id='switch-a', assembly_id='switch-a',
        box_2d=[10, 10, 20, 20], device_class='switch')
    reviewed = ElectricalChoice(observation=original.model_copy(update={
        'gang_count': int(sku[-1]), 'switching_function': 'one_way'}),
        selected_sku=sku, box_item_id='UTB01', box_compatibility_confirmed=True)
    receipt = boundary.issue_review(raw, 'test-user', [original], provider='template', model='offline')
    review = boundary.confirm_review(dict(receipt=receipt, confirmed=True,
        estimate_scope='reviewed_device_allowances', choices=[reviewed.model_dump()]), raw, 'test-user')
    p = boundary.reviewed_plan(review)
    result = estimate_plan(p, catalog)
    assert {line.item_id: line.quantity for line in result.line_items} == {sku: 1, 'UTB01': 1}
    assert allowances(result) == {}
    snap = EstimateInputSnapshot(plan=p, params=EstimatingParams(), prices=snapshot_catalog(catalog, result.priced_at))
    restored = EstimateInputSnapshot.model_validate_json(snap.model_dump_json())
    saved = restored.plan.electrical_review
    assert saved.proposed[0].gang_count is None
    assert saved.proposed[0].switching_function is None
    assert saved.choices[0].observation.gang_count == int(sku[-1])
    assert saved.choices[0].observation.switching_function == 'one_way'
    assert saved.proposed[0].box_2d == saved.choices[0].observation.box_2d
    assert saved.proposed[0].assembly_id == saved.choices[0].observation.assembly_id
    assert recalculate(restored, EstimateCorrections()).estimate.grand_total == result.grand_total
