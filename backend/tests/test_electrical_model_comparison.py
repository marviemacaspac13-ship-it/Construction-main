from scripts.score_electrical_models import score
import asyncio
import hashlib
import io
import json
from unittest.mock import AsyncMock

from PIL import Image
import pytest
from scripts import compare_electrical_models as comparison


def point(identifier,x,kind='light_point'):
    return dict(id=identifier,device_class=kind,box_2d=[490,x-10,510,x+10])


def test_matching_uses_locations_and_classes_not_equal_counts():
    reference=[point('a',100),point('b',300)]
    result=score(reference,[point('x',100,'switch'),point('y',800)],1000,1000,20)
    assert (result['correct'],result['false_or_misplaced'],result['missed'])==(0,2,2)


def test_duplicate_cannot_cover_another_device():
    result=score([point('a',100),point('b',300)],
        [point('x',100),point('duplicate',100)],1000,1000,20)
    assert (result['correct'],result['false_or_misplaced'],result['missed'])==(1,1,1)


def test_matching_avoids_greedy_assignment_losing_a_valid_pair():
    # A can use X or Y, B can only use X. Nearest-edge greedy would lose B.
    result=score([point('a',100),point('b',80)],[point('x',99),point('y',120)],1000,1000,20)
    assert result['correct']==2


def frozen_run(tmp_path,monkeypatch):
    monkeypatch.setattr(comparison,'BACKEND',tmp_path)
    monkeypatch.setenv('GEMINI_API_KEY','offline-test-key')
    image=io.BytesIO();Image.new('RGB',(100,100),'white').save(image,'PNG')
    raw=image.getvalue();(tmp_path/'plan.png').write_bytes(raw)
    models=['gemini-3.8-flash','gemini-3.6-flash','gemini-3.5-flash-lite',
        'gemini-3.1-flash-lite','gemini-2.5-flash']
    (tmp_path/'manifest.json').write_text(json.dumps(dict(models=models,request_budget=5,
        requests_per_model=1,model_timeout_seconds=60,image='plan.png',source_sha256=hashlib.sha256(raw).hexdigest())))
    return models


def test_batch_stops_at_quota_and_repeated_invocation_never_retries(tmp_path,monkeypatch):
    frozen_run(tmp_path,monkeypatch)
    call=AsyncMock(return_value={'available':False,'attempts':[{'outcome':'http_429'}]})
    monkeypatch.setattr(comparison.vision,'find_proposals',call)
    asyncio.run(comparison.run(tmp_path))
    assert call.await_count==1
    with pytest.raises(FileExistsError):asyncio.run(comparison.run(tmp_path))
    assert call.await_count==1


def test_batch_runs_each_model_once_in_frozen_order(tmp_path,monkeypatch):
    import os
    models=frozen_run(tmp_path,monkeypatch)
    observed=[]
    async def provider(*args):
        observed.append(os.environ['ELECTRICAL_GEMINI_MODELS'])
        return {'available':True,'proposed':[],'attempts':[],'receipt':'private-do-not-persist'}
    monkeypatch.setattr(comparison.vision,'find_proposals',provider)
    asyncio.run(comparison.run(tmp_path))
    assert observed==models
    assert 'private-do-not-persist' not in (tmp_path/f'{models[0]}.json').read_text()
