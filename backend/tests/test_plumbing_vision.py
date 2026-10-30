import asyncio
from copy import deepcopy
import hashlib
import io
import json
import time
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
import pytest
import httpx

from app.main import app, _read_plumbing
from app import plumbing_vision as vision
from app.plan_assets import inspect_image
from app.plumbing_models import FixtureProposal
from app.takeoff.schema import FixtureTagObservation, PlanSchema
from app.takeoff.contracts import EstimateInputSnapshot, EstimateCorrections, snapshot_catalog
from app.takeoff.corrections import recalculate
from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams

client = TestClient(app)


@pytest.fixture
def image():
    buffer = io.BytesIO()
    Image.new('RGB', (120, 80), 'white').save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('PLUMBING_VISION_ENABLED', 'true')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('PLUMBING_GEMINI_MODELS', 'first,second')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('PLUMBING_OPENROUTER_MODELS', 'other/vision:free')


def response():
    return {'fixtures': [
        {'id': 'WC-1', 'fixture_class': 'WC', 'box_2d': [100,100,200,200], 'uncertainty': None},
        {'id': 'LAV-1', 'fixture_class': 'LAV', 'box_2d': [100,400,200,500], 'uncertainty': None},
    ], 'limitations': []}


def propose(image, call=None):
    with patch.object(vision, 'call_model', call or AsyncMock(return_value=json.dumps(response()))):
        result = client.post('/api/plumbing/proposals', files={'file': ('plan.png', image, 'image/png')})
    assert result.status_code == 200, result.text
    return result.json()


def confirmation(result):
    return {'receipt': result['receipt'], 'confirmed': True, 'fixtures': result['fixtures']}


def test_disabled_is_original_reader_without_network(image, monkeypatch):
    monkeypatch.setenv('PLUMBING_VISION_ENABLED', 'false')
    call = AsyncMock(side_effect=AssertionError('network'))
    result = propose(image, call)
    assert result['available'] is False
    call.assert_not_called()


def test_fallback_order_is_decided_in_backend(image, configured):
    call = AsyncMock(side_effect=[TimeoutError(), '{bad json', json.dumps(response())])
    result = propose(image, call)
    assert [(a['provider'],a['model']) for a in result['attempts']] == [('gemini','first'),('gemini','second'),('openrouter','other/vision:free')]
    assert result['provider'] == 'openrouter'


def test_all_models_fail_or_empty_uses_original_reader(image, configured):
    result = propose(image, AsyncMock(return_value='{"fixtures":[],"limitations":[]}'))
    assert not result['available'] and len(result['attempts']) == 3
    assert result['receipt'] is None


def test_frontend_cannot_choose_a_different_model(image, configured):
    first = propose(image)
    call = AsyncMock(return_value=json.dumps(response()))
    with patch.object(vision,'call_model',call):
        second = client.post('/api/plumbing/proposals',files={'file':('plan.png',image,'image/png')},data={'after_receipt':first['receipt']}).json()
    assert second['model'] == 'first'
    assert call.await_args.args[2] == 'first'
    schema=client.get('/openapi.json').json()
    ref=schema['paths']['/api/plumbing/proposals']['post']['requestBody']['content']['multipart/form-data']['schema']['$ref'].split('/')[-1]
    assert set(schema['components']['schemas'][ref]['properties'])=={'file'}


@pytest.mark.parametrize('box', [[200,100,100,200],[-1,0,100,100],[0,0,1001,100],[0,0,float('nan'),100],[False,0,100,100]])
def test_bad_coordinates_refused(box):
    body = response(); body['fixtures'][0]['box_2d'] = box
    with pytest.raises(ValueError):
        vision.parse_proposals(json.dumps(body))


def test_duplicate_suppression_and_cross_class_ambiguity():
    body = response()
    body['fixtures'] += [deepcopy(body['fixtures'][0]), {**body['fixtures'][0], 'fixture_class':'LAV'}]
    fixtures, notes = vision.parse_proposals(json.dumps(body))
    assert len(fixtures) == 3
    assert notes and len({f.id for f in fixtures}) == 3


def test_review_requires_confirmation_and_image_owner_signature(image, configured):
    result = propose(image); submitted = confirmation(result)
    for changes in [{'confirmed':False},{'confirmed':1},{'receipt':submitted['receipt']+'x'}]:
        with pytest.raises(HTTPException):
            vision.validate_review(json.dumps({**submitted,**changes}),image,'test-user')
    with pytest.raises(HTTPException):
        vision.validate_review(json.dumps(submitted),image,'another-user')
    with pytest.raises(HTTPException):
        vision.validate_review(json.dumps(submitted),image+b'other','test-user')
    source = vision.read_receipt(result['receipt'],'test-user',hashlib.sha256(image).hexdigest())
    source['issued_at'] = time.time()-14401
    with pytest.raises(HTTPException):
        vision.validate_review(json.dumps({**submitted,'receipt':vision.sign_receipt(source)}),image,'test-user')


def test_review_rejects_duplicates_but_accepts_relabel_add_remove(image, configured):
    result = propose(image); submitted=confirmation(result)
    submitted['fixtures'].append({**submitted['fixtures'][0],'id':'duplicate'})
    with pytest.raises(HTTPException):
        vision.validate_review(json.dumps(submitted),image,'test-user')
    submitted['fixtures']=[{**result['fixtures'][0],'fixture_class':'LAV'}, {'id':'manual','fixture_class':'WC','box_2d':[400,400,450,450]}]
    reviewed=vision.validate_review(json.dumps(submitted),image,'test-user')
    assert reviewed.accepted[0].fixture_class=='LAV'
    assert reviewed.proposed[0].fixture_class=='WC'
    assert reviewed.model=='first'


def test_replacement_preserves_unrelated_counts_and_ocr_observations(image, configured):
    result=propose(image)
    review=vision.validate_review(json.dumps(confirmation(result)),image,'test-user')
    observations=[FixtureTagObservation(tag=tag,x_px=1,y_px=1,score=.8) for tag in ['water_closet','lavatory','floor_drain']]
    counts,remaining=vision.apply_review({'water_closet':99,'lavatory':88,'floor_drain':3,'urinal':2},observations,review)
    # Under prompt v2 a Gemini review also covers urinals, so the label read of 2 is
    # replaced by the review's confirmed 0; floor drains stay label-only.
    assert counts == {'water_closet':1,'lavatory':1,'floor_drain':3,'urinal':0,'kitchen_sink':0,'shower':0,'bathtub':0,'washing_machine':0}
    assert [o.tag for o in remaining] == ['floor_drain']


def test_confirmed_small_plan_survives_original_refusal_and_snapshot_replay(image, configured, catalog):
    result=propose(image)
    submitted=confirmation(result)
    with patch('app.main.read_tiled',return_value=[]), patch('app.main.load_catalog',return_value=catalog):
        original=client.post('/api/estimate/image',files={'file':('plan.png',image,'image/png')},data={'plan_type':'Plumbing Plan'})
        assert original.status_code==422
        reviewed=client.post('/api/estimate/image',files={'file':('plan.png',image,'image/png')},data={'plan_type':'Plumbing Plan','fixture_review':json.dumps(submitted)})
    assert reviewed.status_code==200,reviewed.text
    snapshot=EstimateInputSnapshot.model_validate(reviewed.json()['original_input'])
    assert snapshot.plan.fixture_tags == {'water_closet':1,'lavatory':1,'urinal':0,'kitchen_sink':0,'shower':0,'bathtub':0,'washing_machine':0}
    assert snapshot.plan.fixture_review.accepted[0].id==result['fixtures'][0]['id']
    assert reviewed.json()['estimate']['grand_total']>0
    replay=recalculate(snapshot,EstimateCorrections())
    assert replay.estimate.grand_total==reviewed.json()['estimate']['grand_total']
    assert replay.effective_input.plan.fixture_review==snapshot.plan.fixture_review
    assert not any('Counts come from reading printed fixture tags' in s for s in replay.estimate.assumptions)


def test_final_original_reader_keeps_minimum_guard(image):
    with patch('app.main.read_tiled',return_value=[]),pytest.raises(HTTPException) as refusal:
        _read_plumbing(image,'Plumbing Plan')
    assert refusal.value.status_code==422


def test_removing_all_proposals_does_not_validate_sparse_ocr(image, configured):
    from app.extract.tags import TagCount
    result=propose(image)
    review=vision.validate_review(json.dumps({**confirmation(result),'fixtures':[]}),image,'test-user')
    with patch('app.main.read_tiled',return_value=[]),patch('app.main.count_tags',return_value={'floor_drain':TagCount(tag='floor_drain',count=1)}),pytest.raises(HTTPException) as refusal:
        _read_plumbing(image,'Plumbing Plan',review)
    assert refusal.value.status_code==422


def test_invalid_image_never_reaches_provider(configured):
    call=AsyncMock(side_effect=AssertionError('network'))
    with patch.object(vision,'call_model',call):
        result=client.post('/api/plumbing/proposals',files={'file':('bad.png',b'not an image','image/png')})
    assert result.status_code==400
    call.assert_not_called()


@pytest.mark.parametrize('provider',['gemini','openrouter'])
def test_provider_http_shapes_and_truncated_results(provider, configured):
    async def run():
        captured=[]
        def handler(request):
            captured.append(request)
            if provider=='gemini':
                return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(response())}]}}]})
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(response())}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
            text=await vision.call_model(transport,provider,'chosen','encoded-image')
        assert len(vision.parse_proposals(text)[0])==2
        body=json.loads(captured[0].content)
        if provider=='gemini':
            assert captured[0].headers['x-goog-api-key']=='test-not-a-real-key'
            assert body['contents'][0]['parts'][1]['inlineData']['data']=='encoded-image'
        else:
            assert body['model']=='chosen'
            assert body['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
        def truncated(request):
            return httpx.Response(200,json={'candidates':[{'finishReason':'MAX_TOKENS'}], 'choices':[{'finish_reason':'length'}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(truncated)) as transport:
            with pytest.raises(ValueError):
                await vision.call_model(transport,provider,'chosen','encoded-image')
    asyncio.run(run())


def test_provider_body_limit():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'x'*1_000_001))) as transport:
            with pytest.raises(ValueError):
                await vision.post_json(transport,'https://example.com')
    asyncio.run(run())


@pytest.mark.parametrize('field,amount', [('fixtures', 501), ('limitations', 31)])
def test_local_limits_remain_enforced_without_provider_array_limits(field, amount):
    body = response()
    body[field] = ([deepcopy(body['fixtures'][0]) for _ in range(amount)]
                   if field == 'fixtures' else ['needs checking'] * amount)
    with pytest.raises(ValueError):
        vision.parse_proposals(json.dumps(body))


def test_review_preserved_through_immutable_save(image, configured, catalog, monkeypatch):
    monkeypatch.setenv('ESTIMATE_REVISIONS_ENABLED','true')
    proposal=propose(image)
    with patch('app.main.read_tiled',return_value=[]),patch('app.main.load_catalog',return_value=catalog):
        result=client.post('/api/estimate/image',files={'file':('plan.png',image,'image/png')},data={'plan_type':'Plumbing Plan','fixture_review':json.dumps(confirmation(proposal))}).json()
    request={'project_id':'00000000-0000-0000-0000-000000000001',
        'precondition':{'expected_active_revision_id':None,'idempotency_key':'00000000-0000-0000-0000-000000000002'},
        'asset':{'source_sha256':hashlib.sha256(image).hexdigest(),'original_filename':'plan.png','media_type':'image/png','byte_size':len(image)},
        'result':result}
    with patch('app.revisions.rpc',return_value='00000000-0000-0000-0000-000000000003') as store:
        saved=client.post('/api/estimate/revisions',json=request)
    assert saved.status_code==200,saved.text
    persisted=store.call_args.args[1]['p_result']
    reopened=EstimateInputSnapshot.model_validate(persisted['original_input'])
    assert len(reopened.plan.fixture_review.accepted)==2
    assert reopened.plan.fixture_review.source_sha256==hashlib.sha256(image).hexdigest()
