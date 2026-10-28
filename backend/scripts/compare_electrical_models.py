"""Run a frozen, explicitly authorized five-model development comparison once.

No retries, local aggregation or estimate writes. Auth/quota errors stop the batch.
"""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from dotenv import load_dotenv
from app import electrical_vision as vision
from app.plan_assets import inspect_image


async def run(directory):
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    models=manifest['models']
    if len(models)!=len(set(models)) or not 1<=len(models)<=5 or any(m not in vision.FREE_TIER_MODELS for m in models):
        raise ValueError('Only the five reviewed free-tier model names are allowed once each.')
    if manifest['request_budget']!=len(models) or manifest['requests_per_model']!=1 or manifest['model_timeout_seconds']!=vision.MODEL_TIMEOUT_SECONDS:
        raise ValueError('Request policy differs from frozen manifest.')
    raw=(BACKEND/manifest['image']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest['source_sha256']:
        raise ValueError('Original image changed.')
    metadata=inspect_image(raw,Path(manifest['image']).name,'image/png')
    load_dotenv(BACKEND/'.env')
    if not os.getenv('GEMINI_API_KEY'):raise ValueError('Existing Gemini key is required.')
    # Exclusive marker prevents an interrupted or repeated invocation retrying requests.
    with (directory/'run-started.json').open('x',encoding='utf-8') as f:
        json.dump(dict(at=datetime.now(timezone.utc).isoformat(),manifest_sha256=hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest()),f)
    os.environ['ELECTRICAL_VISION_ENABLED']='true'
    results=[]
    for model in models:
        os.environ['ELECTRICAL_GEMINI_MODELS']=model
        print(json.dumps({'starting_model':model}),flush=True)
        started=time.monotonic()
        result=await vision.find_proposals(raw,metadata,'electrical-model-comparison')
        result.pop('receipt',None)
        record=dict(model=model,elapsed_ms=round((time.monotonic()-started)*1000),
            source_sha256=metadata['source_sha256'],result=result,accuracy_verified=False)
        with (directory/f'{model}.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
        summary=dict(model=model,available=result['available'],elapsed_ms=record['elapsed_ms'],
            classes=dict(Counter(o['device_class'] for o in result.get('proposed',[]))),attempts=result['attempts'])
        results.append(summary)
        print(json.dumps(summary),flush=True)
        if any(a['outcome'] in {'http_400','http_401','http_403','http_413','http_429'} for a in result['attempts']):
            print('Stopped batch after account, quota or rejected-request response.',flush=True)
            break
    with (directory/'run-summary.json').open('x',encoding='utf-8') as f:json.dump(results,f,indent=2)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    asyncio.run(run(parser.parse_args().directory))
