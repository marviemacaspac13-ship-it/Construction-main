"""Offline review boundaries: semantics, signed provenance and snapshot replay."""
from app.revisions import sign_original_input
from copy import deepcopy
import hashlib
import io
import json
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
import pytest

from app import audit, electrical_review as boundary
from app.electrical_models import ElectricalObservation, ElectricalChoice, ElectricalReview, assess
from app.main import app
from app.takeoff.contracts import EstimateCorrections, EstimateInputSnapshot, snapshot_catalog
from app.takeoff.corrections import recalculate
from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import FixtureCount, PlanSchema


@pytest.fixture
def raw():
    buffer = io.BytesIO()
    Image.new('RGB', (100, 80), 'white').save(buffer, 'PNG')
    return buffer.getvalue()


def observation(id='a', **changes):
    return ElectricalObservation.model_validate(dict(id=id, assembly_id=id,
        box_2d=[10, 10, 20, 20], device_class='convenience_outlet',
        socket_configuration='duplex', **changes))


def proposal(id='a', **changes):
    data=observation(id).model_dump()
    data.update(changes)
    return ElectricalObservation.model_validate(data)


def confirmed(raw, choices=None, proposed=None, owner='test-user'):
    proposed = [proposal()] if proposed is None else proposed
    choices = [ElectricalChoice(observation=p) for p in proposed] if choices is None else choices
    receipt = boundary.issue_review(raw, owner, proposed, provider='template', model='offline-fixture')
    return boundary.confirm_review(dict(receipt=receipt, confirmed=True,
        choices=[c.model_dump() for c in choices]), raw, owner)


@pytest.mark.parametrize('change', [
    {'box_2d':[-1,0,1,1]}, {'box_2d':[0,0,1001,1]}, {'box_2d':[1,0,1,1]},
    {'box_2d':[0,0,float('nan'),1]}, {'box_2d':[False,0,1,1]},
    {'gang_count':True}, {'gang_count':1.5}, {'gang_count':0},
    {'device_class':'WC'}, {'catalog_sku':'SW03'}, {'price':3}, {'id':'../bad'},
])
def test_proposals_refuse_invalid_geometry_types_and_model_price_fields(change):
    with pytest.raises(ValidationError):
        proposal(**change)


@pytest.mark.parametrize('cls,mark,sku', [
    ('switch','S3w','SW03'), ('switch','S2','GS02'), ('ac_outlet','ACU','ACO01'),
    ('unknown','illegible',None),
])
def test_unsupported_types_remain_unresolved_not_nearest_product(raw, cls, mark, sku):
    o=proposal(device_class=cls,raw_mark=mark,socket_configuration=None)
    review=confirmed(raw,[ElectricalChoice(observation=o,selected_sku=sku)],[o])
    assert review.unresolved()[0].observation_id=='a'
    assert review.priced_counts()=={}
    assert review.choices[0].observation.raw_mark==mark
    with pytest.raises(ValueError,match='Resolve or explicitly exclude'):
        boundary.reviewed_plan(review)


def test_owner_default_is_not_a_read_gang_and_single_socket_does_not_infer_sku():
    default=assess(ElectricalChoice(observation=proposal()))
    assert (default.item_id,default.basis)==('OT01','owner_selected_duplex_default_not_read_gang')
    assert proposal().gang_count is None
    for socket in ('single','triplex',None):
        assert assess(ElectricalChoice(observation=proposal(socket_configuration=socket))).state=='unresolved'


def test_explicit_product_must_match_family_and_confirmed_attributes():
    assert assess(ElectricalChoice(observation=proposal(),selected_sku='OT02')).item_id=='OT02'
    assert assess(ElectricalChoice(observation=proposal(gang_count=2),selected_sku='OT01')).state=='unresolved'
    assert assess(ElectricalChoice(observation=proposal(),selected_sku='CLR03')).state=='unresolved'
    light=proposal(device_class='light_point',socket_configuration=None)
    assert assess(ElectricalChoice(observation=light)).item_id=='CLR01'
    assert assess(ElectricalChoice(observation=light,selected_sku='CLR03')).item_id=='CLR03'


def test_exclusion_is_explicit_and_retains_unsupported_evidence(raw):
    switch=proposal('s',device_class='switch',raw_mark='S3w',socket_configuration=None,box_2d=[30,30,40,40])
    choices=[ElectricalChoice(observation=proposal()),ElectricalChoice(observation=switch,
        disposition='exclude',exclusion_reason='Outside this estimate; needs an approved product and circuit rule.')]
    review=confirmed(raw,choices,[proposal(),switch])
    assert review.priced_counts()=={'OT01':1}
    assert [a.state for a in review.assessments()]==['priced','excluded']
    assert boundary.reviewed_plan(review).fixtures==[FixtureCount(item_id='OT01',count=1)]
    with pytest.raises(ValidationError,match='need a reason'):
        ElectricalChoice(observation=switch,disposition='exclude')
    with pytest.raises(ValueError,match='Every original proposal'):
        confirmed(raw,[choices[0]],[proposal(),switch])


def test_empty_or_all_excluded_review_is_not_a_zero_estimate(raw):
    review=confirmed(raw,[],[])
    with pytest.raises(ValueError,match='no supported'):
        boundary.reviewed_plan(review)
    review=confirmed(raw,[ElectricalChoice(observation=proposal(),disposition='exclude',exclusion_reason='Legend')])
    with pytest.raises(ValueError,match='no supported'):
        boundary.reviewed_plan(review)


@pytest.mark.parametrize('second', [
    {'id':'a','assembly_id':'b','box_2d':[30,30,40,40]},
    {'id':'b','assembly_id':'a','box_2d':[30,30,40,40]},
    {'id':'b','assembly_id':'b','box_2d':[10,10,20,20]},
])
def test_duplicate_identity_assembly_and_overlap_are_refused(raw, second):
    b=proposal(**second)
    with pytest.raises(ValueError):
        confirmed(raw,[ElectricalChoice(observation=proposal()),ElectricalChoice(observation=b)],[])


def test_review_supports_user_add_move_and_relabel_without_adding_matcher_totals(raw):
    revised=proposal(box_2d=[20,20,30,30],socket_configuration=None,device_class='light_point')
    added=proposal('new',box_2d=[50,50,60,60])
    review=confirmed(raw,[ElectricalChoice(observation=revised),ElectricalChoice(observation=added)])
    assert review.proposed[0].device_class=='convenience_outlet'
    assert review.priced_counts()=={'CLR01':1,'OT01':1}
    assert sum(f.count for f in boundary.reviewed_plan(review).fixtures)==2


def test_owner_image_signature_expiry_and_explicit_confirmation(raw, monkeypatch):
    monkeypatch.setenv('ELECTRICAL_REVIEW_SECRET','offline-secret')
    monkeypatch.setattr(boundary.time,'time',lambda:1000)
    token=boundary.issue_review(raw,'owner-a',[proposal()],provider='template',model='local')
    body=dict(receipt=token,confirmed=True,choices=[ElectricalChoice(observation=proposal()).model_dump()])
    assert boundary.confirm_review(body,raw,'owner-a').owner_id=='owner-a'
    for receipt,owner in [(token,'owner-b'),(token+'x','owner-a')]:
        with pytest.raises(ValueError):
            boundary.confirm_review({**body,'receipt':receipt},raw,owner)
    buffer=io.BytesIO();Image.new('RGB',(100,80),'black').save(buffer,'PNG')
    with pytest.raises(ValueError):
        boundary.confirm_review(body,buffer.getvalue(),'owner-a')
    with pytest.raises(ValueError):
        boundary.confirm_review({**body,'confirmed':False},raw,'owner-a')
    monkeypatch.setattr(boundary.time,'time',lambda:15400)
    with pytest.raises(ValueError):
        boundary.confirm_review(body,raw,'owner-a')
    monkeypatch.setattr(boundary.time,'time',lambda:999)
    with pytest.raises(ValueError):
        boundary.confirm_review(body,raw,'owner-a')


def test_replay_numeric_overrides_reset_and_audit_keep_original_boxes(raw,catalog,tmp_path,monkeypatch):
    plan=boundary.reviewed_plan(confirmed(raw))
    original=EstimateInputSnapshot(plan=plan,params=EstimatingParams(),prices=snapshot_catalog(catalog,'2026-10-26T00:00:00Z'))
    restored=EstimateInputSnapshot.model_validate_json(original.model_dump_json())
    before=estimate_plan(restored.plan,restored.prices.to_catalog())
    changed=recalculate(restored,EstimateCorrections(quantities={'electrical_counts':{'OT01':3}}))
    assert changed.effective_input.plan.electrical_review==original.plan.electrical_review
    assert next(f.count for f in changed.effective_input.plan.fixtures if f.item_id=='OT01')==3
    reset=recalculate(restored,EstimateCorrections()).estimate
    assert reset.grand_total==before.grand_total
    monkeypatch.setattr(audit,'RUNS_DIR',tmp_path);monkeypatch.setattr(audit,'LEDGER',tmp_path/'audit.jsonl')
    audit.record_estimate('Electrical Plan',changed.estimate,plan=changed.effective_input.plan)
    record=json.loads((tmp_path/'audit.jsonl').read_text())
    assert record['electrical_review']['proposed']==[proposal().model_dump(mode='json')]
    assert record['electrical_review_assessments'][0]['item_id']=='OT01'
    assert any('explicitly reviewed' in a for a in before.assumptions)
    assert not any('WC/LAV' in a for a in before.assumptions)


def test_review_cannot_be_attached_to_wrong_trade_or_activate_hidden_products(raw,catalog):
    plan=boundary.reviewed_plan(confirmed(raw))
    for change in [{'plan_type':'Plumbing Plan'}, {'fixtures':[{'item_id':'SW03','count':1}]}]:
        with pytest.raises(ValueError):
            PlanSchema.model_validate({**plan.model_dump(),**change})
    # Even Python callers bypassing Pydantic cannot price a new switch class.
    bypass=plan.model_copy(update={'fixtures':[FixtureCount(item_id='ACO01',count=1)]})
    with pytest.raises(ValueError):
        estimate_plan(bypass,catalog)


def test_legacy_snapshots_do_not_gain_a_null_evidence_key():
    plan=PlanSchema(plan_type='Electrical Plan',fixtures=[FixtureCount(item_id='OT01',count=2)])
    data=plan.model_dump()
    assert 'electrical_review' not in data
    assert PlanSchema.model_validate(data).model_dump()==data


def save_payload(raw,catalog,review):
    plan=boundary.reviewed_plan(review)
    estimate=estimate_plan(plan,catalog)
    snapshot=EstimateInputSnapshot(plan=plan,params=EstimatingParams(),prices=snapshot_catalog(catalog,estimate.priced_at))
    sha=hashlib.sha256(raw).hexdigest()
    return dict(project_id=str(uuid4()),precondition=dict(expected_active_revision_id=None,idempotency_key=str(uuid4())),
        asset=dict(source_sha256=sha,original_filename='test.png',media_type='image/png',byte_size=len(raw)),
        result=dict(original_input=snapshot.model_dump(mode='json'),scan=dict(source_sha256=sha,method='detection'),
            estimate=estimate.model_dump(),extraction=None,unmatched_detections=[],
            input_signature=sign_original_input(snapshot,sha,'test-user')))


def test_mock_revision_save_preserves_review_and_rejects_mismatches(raw,catalog,monkeypatch):
    monkeypatch.setenv('ESTIMATE_REVISIONS_ENABLED','true')
    payload=save_payload(raw,catalog,confirmed(raw))
    with patch('app.revisions.rpc',return_value=str(uuid4())) as rpc:
        r=TestClient(app).post('/api/estimate/revisions',json=payload)
        assert r.status_code==200,r.text
        saved=rpc.call_args.args[1]['p_result']['original_input']['plan']['electrical_review']
        assert ElectricalReview.model_validate(saved).priced_counts()=={'OT01':1}
    for change in ('owner','hash','counts'):
        data=deepcopy(payload); p=data['result']['original_input']['plan']
        if change=='owner': p['electrical_review']['owner_id']='different-user'
        if change=='hash': p['electrical_review']['source_sha256']='a'*64
        if change=='counts': p['fixtures'][0]['count']=2
        with patch('app.revisions.rpc') as rpc:
            assert TestClient(app).post('/api/estimate/revisions',json=data).status_code==422
            rpc.assert_not_called()
