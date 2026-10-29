"""Offline Gemini proposal and automatic local fallback boundaries."""
from copy import deepcopy
import asyncio
import io
import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import httpx
from PIL import Image
import pytest

from app import electrical_vision as vision, electrical_review as boundary
from app.electrical_models import ElectricalChoice, ElectricalReview
from app.main import app
from app.plan_assets import inspect_image
from app.schemas import Detection


@pytest.fixture
def raw():
    buffer=io.BytesIO();Image.new('RGB',(120,80),'white').save(buffer,'PNG');return buffer.getvalue()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('ELECTRICAL_VISION_ENABLED','true')
    monkeypatch.setenv('GEMINI_API_KEY','offline-test-key')
    monkeypatch.setenv('ELECTRICAL_GEMINI_MODELS','gemini-2.5-flash,gemini-3.5-flash-lite')


def response():
    return {'observations':[dict(id='s',assembly_id='s',box_2d=[100,100,200,200],
        device_class='switch',raw_mark='S2',adjacent_text='S2',socket_configuration=None,
        gang_count=2,switching_function='one_way',uncertainty='Check legend and gang count.')],
        'limitations':['Small marks may be unreadable.']}


def propose(raw,call):
    with patch.object(vision,'call_model',call):
        result=TestClient(app).post('/api/electrical/proposals',files={'file':('plan.png',raw,'image/png')})
    assert result.status_code==200,result.text
    return result.json()


def test_gemini_is_primary_and_success_does_not_run_or_add_local_detection(raw,configured):
    call=AsyncMock(return_value=(json.dumps(response()),'gemini-2.5-flash'))
    with patch('app.main.match_templates',side_effect=AssertionError('local must not run')):
        result=propose(raw,call)
    assert result['provider']=='gemini' and len(result['proposed'])==1
    assert result['proposed'][0]['raw_mark']=='S2'
    assert result['proposed'][0]['gang_count']==2
    assert result['attempts'][0]['returned_model']=='gemini-2.5-flash'
    assert call.await_count==1
    c=ElectricalChoice(observation=result['proposed'][0],selected_sku='SW02',
        box_exclusion_reason='Box dimensions unavailable')
    review=boundary.confirm_review(dict(receipt=result['receipt'],confirmed=True,
        estimate_scope='devices_and_boxes',choices=[c.model_dump()]),raw,'test-user')
    restored=ElectricalReview.model_validate_json(review.model_dump_json())
    assert restored.provider=='gemini' and restored.prompt_version==vision.PROMPT_VERSION
    assert restored.attempts[0].outcome=='proposed' and restored.limitations
    assert boundary.reviewed_plan(restored).fixtures[0].item_id=='SW02'


def test_light_location_is_aligned_without_losing_original_model_evidence(raw,configured,catalog):
    body=response()
    body['observations'][0].update(device_class='light_point',raw_mark=None,adjacent_text=None,
        gang_count=None,switching_function=None,uncertainty=None)
    original=deepcopy(body['observations'][0])
    anchor=Detection(label='CLR01',confidence=.9,bbox=[12,10,28,26])
    with patch('app.vision.template_match.match_templates',return_value=[anchor]):
        result=propose(raw,AsyncMock(return_value=(json.dumps(body),'gemini-3.5-flash-lite')))
    assert result['provider']=='gemini'
    assert result['proposed'][0]['box_2d']==[125,100,325,28/120*1000]
    assert len(result['proposed'])==1
    choice=ElectricalChoice(observation=result['proposed'][0],selected_sku='CLR01',
        box_exclusion_reason='Test scope: no confirmed box fit')
    reviewed=boundary.confirm_review(dict(receipt=result['receipt'],confirmed=True,
        estimate_scope='reviewed_device_allowances',choices=[choice.model_dump()]),raw,'test-user')
    assert list(reviewed.proposed[0].box_2d)==original['box_2d']
    assert reviewed.choices[0].observation.box_2d!=reviewed.proposed[0].box_2d
    assert any('aligned' in line for line in reviewed.limitations)
    from app.takeoff.estimator import estimate_plan
    before=boundary.confirm_review(dict(receipt=result['receipt'],confirmed=True,
        estimate_scope='reviewed_device_allowances',choices=[{**choice.model_dump(),'observation':reviewed.proposed[0].model_dump()}]),raw,'test-user')
    assert estimate_plan(boundary.reviewed_plan(before),catalog).grand_total==estimate_plan(boundary.reviewed_plan(reviewed),catalog).grand_total


def test_owned_alternative_refinement_preserves_signed_raw_inventory_and_price(raw,configured,catalog):
    body=response();body['observations']=[]
    for identifier,(x,y,x2,y2) in [('ambiguous',(43,34,45,36)),('strong',(50,30,60,40))]:
        body['observations'].append(dict(id=identifier,assembly_id=identifier,
            box_2d=[y/80*1000,x/120*1000,y2/80*1000,x2/120*1000],device_class='light_point',
            raw_mark=None,adjacent_text=None,socket_configuration=None,gang_count=None,
            switching_function=None,uncertainty=None))
    original=deepcopy(body['observations'])
    anchors=[Detection(label='CLR01',confidence=.9,bbox=[30,30,40,40]),
             Detection(label='CLR01',confidence=.9,bbox=[50,30,60,40])]
    call=AsyncMock(return_value=(json.dumps(body),'gemini-3.5-flash-lite'))
    with patch('app.vision.template_match.match_templates',return_value=anchors):
        result=propose(raw,call)
    assert call.await_count==1
    assert len(result['proposed'])==len(original)==2
    assert result['proposed'][0]['box_2d']==[375,250,500,40/120*1000]
    choices=[ElectricalChoice(observation=o,selected_sku='CLR01',box_exclusion_reason='Test scope')
             for o in result['proposed']]
    review=boundary.confirm_review(dict(receipt=result['receipt'],confirmed=True,
        estimate_scope='reviewed_device_allowances',choices=[c.model_dump() for c in choices]),raw,'test-user')
    # parse_proposals normalizes IDs, so check original raw attributes/locations independently.
    assert [list(o.box_2d) for o in review.proposed]==[o['box_2d'] for o in original]
    assert all(o.device_class=='light_point' for o in review.proposed)
    before_choices=[{**c.model_dump(),'observation':o.model_dump()} for c,o in zip(choices,review.proposed)]
    before=boundary.confirm_review(dict(receipt=result['receipt'],confirmed=True,
        estimate_scope='reviewed_device_allowances',choices=before_choices),raw,'test-user')
    from app.takeoff.estimator import estimate_plan
    assert estimate_plan(boundary.reviewed_plan(before),catalog).grand_total==estimate_plan(boundary.reviewed_plan(review),catalog).grand_total


def test_optional_alignment_failure_keeps_gemini_inventory_without_another_request(raw,configured):
    call=AsyncMock(return_value=(json.dumps(response()),'gemini-3.5-flash-lite'))
    with patch.object(vision,'refine_image_locations',side_effect=RuntimeError('alignment failed')):
        result=propose(raw,call)
    assert result['provider']=='gemini'
    assert call.await_count==1
    assert result['proposed'][0]['box_2d']==response()['observations'][0]['box_2d']
    assert result['proposed'][0]['device_class']=='switch'


def test_timeout_then_next_free_model_succeeds_before_local(raw,configured):
    call=AsyncMock(side_effect=[TimeoutError(),(json.dumps(response()),'gemini-3.5-flash-lite')])
    with patch('app.main.match_templates',side_effect=AssertionError('no local')):
        result=propose(raw,call)
    assert [a['outcome'] for a in result['attempts']]==['timeout','proposed']
    assert result['model']=='gemini-3.5-flash-lite'


@pytest.mark.parametrize('failure', [TimeoutError(),ValueError('secret raw body must not escape'),KeyError('candidates'),
    httpx.HTTPStatusError('private upstream body',request=httpx.Request('POST','https://generativelanguage.googleapis.com/test'),
        response=httpx.Response(503))])
def test_all_provider_failures_automatically_run_local_without_changing_scope(raw,configured,failure):
    call=AsyncMock(side_effect=failure)
    with patch('app.main.match_templates',return_value=[Detection(label='OT01',confidence=.9,bbox=[12,8,24,16])]):
        result=propose(raw,call)
    assert result['provider']=='template' and result['proposed'][0]['device_class']=='convenience_outlet'
    assert len(result['attempts'])==2 and 'Local detection' in result['message']
    assert 'secret raw body' not in json.dumps(result)
    c=ElectricalChoice(observation=result['proposed'][0],selected_sku='OT01',box_exclusion_reason='Unknown fit')
    review=boundary.confirm_review(dict(receipt=result['receipt'],confirmed=True,
        estimate_scope='devices_and_boxes',choices=[c.model_dump()]),raw,'test-user')
    assert review.provider=='template' and len(review.attempts)==2
    assert review.estimate_scope=='devices_and_boxes'


@pytest.mark.parametrize('status',[400,401,403,413,429])
def test_auth_or_quota_failure_stops_further_calls_and_falls_back(raw,configured,status):
    request=httpx.Request('POST','https://generativelanguage.googleapis.com/test')
    error=httpx.HTTPStatusError('must not escape',request=request,response=httpx.Response(status,request=request))
    call=AsyncMock(side_effect=error)
    with patch('app.main.match_templates',return_value=[]):
        result=propose(raw,call)
    assert call.await_count==1 and result['provider']=='template'
    assert result['attempts'][0]['outcome']==f'http_{status}'
    assert result['proposed']==[] # review requires actual additions; no zero-price estimate


@pytest.mark.parametrize('setting',['disabled','missing_key','paid_only'])
def test_unavailable_configuration_is_local_without_network(raw,configured,monkeypatch,setting):
    if setting=='disabled':monkeypatch.setenv('ELECTRICAL_VISION_ENABLED','false')
    elif setting=='missing_key':monkeypatch.delenv('GEMINI_API_KEY')
    else:monkeypatch.setenv('ELECTRICAL_GEMINI_MODELS','gemini-2.5-pro,paid/provider,auto')
    call=AsyncMock(side_effect=AssertionError('network'))
    with patch('app.main.match_templates',return_value=[]):result=propose(raw,call)
    assert result['provider']=='template' and result['attempts']==[]
    call.assert_not_called()


def test_paid_models_and_duplicates_are_not_added_to_fallback_order(monkeypatch):
    monkeypatch.setenv('ELECTRICAL_GEMINI_MODELS','gemini-2.5-pro,gemini-2.5-flash,gemini-2.5-flash,gemini-3.5-flash-lite,auto')
    assert vision.configured_models()==['gemini-2.5-flash','gemini-3.5-flash-lite']


def test_default_uses_verified_replacement_and_ignores_rejected_legacy_model(monkeypatch):
    monkeypatch.delenv('ELECTRICAL_GEMINI_MODELS',raising=False)
    # 3.6 Flash first since the 29 Oct 2026 trial (12/21 reviewed marks vs 2/21).
    assert vision.configured_models()==['gemini-3.6-flash','gemini-3.5-flash-lite']
    monkeypatch.setenv('ELECTRICAL_GEMINI_MODELS','gemini-2.5-flash-lite,gemini-3.5-flash-lite,gemini-flash-latest')
    assert vision.configured_models()==['gemini-3.5-flash-lite']


def test_expanded_free_model_list_keeps_production_attempts_bounded(monkeypatch):
    models=['gemini-3.8-flash','gemini-3.6-flash','gemini-3.5-flash-lite',
        'gemini-3.1-flash-lite','gemini-2.5-flash']
    assert vision.FREE_TIER_MODELS==set(models)
    monkeypatch.setenv('ELECTRICAL_GEMINI_MODELS',','.join(models))
    assert vision.configured_models()==models[:2]


def test_model_deadline_allows_the_observed_23_second_response(raw,configured):
    real_wait=asyncio.wait_for
    deadlines=[]
    async def track_wait(awaitable,timeout):
        deadlines.append(timeout)
        return await real_wait(awaitable,timeout)
    with patch.object(vision.asyncio,'wait_for',track_wait):
        result=propose(raw,AsyncMock(return_value=(json.dumps(response()),'gemini-3.5-flash-lite')))
    assert result['provider']=='gemini'
    assert deadlines==[2,10,60,5]
    assert 23 < vision.MODEL_TIMEOUT_SECONDS < vision.TOTAL_TIMEOUT_SECONDS


def test_provider_error_is_bounded_and_only_safe_category_is_logged():
    async def check():
        async def handler(request):
            return httpx.Response(404,json={'error':{'status':'NOT_FOUND','message':
                'This model is no longer available to new users. private-key private-plan'}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(httpx.HTTPStatusError) as raised:
                await vision.post_json(client,'https://generativelanguage.googleapis.com/test')
        assert raised.value.response.status_code==404
        assert vision.failure_detail(raised.value)=='model_unavailable_to_project'
        assert 'private' not in vision.failure_detail(raised.value)
    asyncio.run(check())


def test_oversized_provider_error_is_not_retained():
    async def check():
        async def handler(request):
            return httpx.Response(503,content=b'x'*1_000_001)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ValueError,match='too large'):
                await vision.post_json(client,'https://generativelanguage.googleapis.com/test')
    asyncio.run(check())


@pytest.mark.parametrize('change',[
    {'box_2d':[-1,0,100,100]}, {'box_2d':[1,1,1,10]}, {'box_2d':[0,0,1001,10]},
    {'box_2d':[0,0,float('nan'),10]}, {'gang_count':True}, {'selected_sku':'SW02'},
    {'price':169}, {'device_class':'toilet'}, {'switching_function':'two_gang'},
])
def test_invalid_or_priced_provider_observations_are_rejected(change):
    body=response();body['observations'][0].update(change)
    with pytest.raises(ValueError):vision.parse_proposals(json.dumps(body))


def test_empty_and_invalid_response_falls_back_not_zero(raw,configured):
    with patch('app.main.match_templates',return_value=[]):
        result=propose(raw,AsyncMock(return_value=('{"observations":[],"limitations":[]}',None)))
    assert result['provider']=='template' and len(result['attempts'])==2


def test_duplicate_semantics_are_deduplicated_but_conflicts_retained():
    body=response();body['observations'].append(deepcopy(body['observations'][0]))
    values,_=vision.parse_proposals(json.dumps(body));assert len(values)==1
    body['observations'][-1]['switching_function']='three_way'
    values,notes=vision.parse_proposals(json.dumps(body))
    assert len(values)==2 and any('Overlapping' in n for n in notes)
    assert len({o.id for o in values})==2


def test_small_three_way_mark_does_not_become_three_gang_priceable_product():
    body=response();body['observations'][0].update(raw_mark='S3w',gang_count=None,switching_function='three_way')
    values,_=vision.parse_proposals(json.dumps(body))
    assert values[0].gang_count is None and values[0].switching_function=='three_way'
    from app.electrical_models import assess
    c=ElectricalChoice(observation=values[0],selected_sku='SW03',box_exclusion_reason='Unknown fit')
    assert assess(c,partial=True).state=='unresolved'


def test_client_has_no_model_or_detector_selector_in_request_contract(raw,configured):
    schema=app.openapi();ref=schema['paths']['/api/electrical/proposals']['post']['requestBody']['content']['multipart/form-data']['schema']['$ref'].split('/')[-1]
    assert set(schema['components']['schemas'][ref]['properties'])=={'file'}


def test_provider_schema_uses_supported_homogeneous_coordinate_array():
    box=vision.SCHEMA['properties']['observations']['items']['properties']['box_2d']
    assert 'prefixItems' not in box
    assert box['items']=={'type':'number','minimum':0,'maximum':1000}
    assert box['minItems']==box['maxItems']==4


def test_expired_or_wrong_owner_gemini_receipt_cannot_be_confirmed(raw,configured):
    result=propose(raw,AsyncMock(return_value=(json.dumps(response()),None)))
    data=dict(receipt=result['receipt'],confirmed=True,choices=[dict(observation=result['proposed'][0])])
    with pytest.raises(ValueError):boundary.confirm_review(data,raw,'other-owner')


def test_transport_uses_electrical_prompt_schema_and_rejects_truncation(raw,configured):
    asyncio.run(check_transport())


async def check_transport():
    # No HTTP request: inspect the transport boundary, with its network helper mocked.
    encoded='offline-image'
    returned={'modelVersion':'gemini-2.5-flash','candidates':[{'finishReason':'STOP',
        'content':{'parts':[{'thought':True,'text':'private reasoning'}, {'text':json.dumps(response())}]}}]}
    with patch.object(vision,'post_json',AsyncMock(return_value=returned)) as post:
        text,version=await vision.call_model(None,'gemini-2.5-flash',encoded)
    assert json.loads(text)==response() and version=='gemini-2.5-flash'
    assert post.await_args.kwargs['json']['contents'][0]['parts'][0]['text']==vision.PROMPT
    assert post.await_args.kwargs['json']['generationConfig']['responseJsonSchema']==vision.SCHEMA
    returned['candidates'][0]['finishReason']='MAX_TOKENS'
    with patch.object(vision,'post_json',AsyncMock(return_value=returned)):
        with pytest.raises(ValueError):await vision.call_model(None,'gemini-2.5-flash',encoded)

