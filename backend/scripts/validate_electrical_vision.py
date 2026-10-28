"""One explicitly requested free-tier-eligible electrical proposal trial.

No retries, catalog/estimate writes or local detection. Saves sanitized proposals
and timings for subsequent visual comparison; never prints credentials/receipts.
"""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
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


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model',choices=sorted(vision.FREE_TIER_MODELS),default=vision.DEFAULT_MODELS.split(',')[0])
    args=parser.parse_args()
    load_dotenv(BACKEND/'.env')
    os.environ['ELECTRICAL_VISION_ENABLED']='true'
    os.environ['ELECTRICAL_GEMINI_MODELS']=args.model # exactly one possible request
    raw=args.image.read_bytes()
    media={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp'}[args.image.suffix.lower()]
    metadata=inspect_image(raw,args.image.name,media)
    started=time.monotonic()
    result=asyncio.run(vision.find_proposals(raw,metadata,'electrical-validation'))
    result.pop('receipt',None)
    record={'recorded_at':datetime.now(timezone.utc).isoformat(),'request_budget':1,
        'requested_model':args.model,'source_sha256':metadata['source_sha256'],
        'image_name':args.image.name,'image_width':metadata['pixel_width'],'image_height':metadata['pixel_height'],
        'elapsed_ms':round((time.monotonic()-started)*1000),'status':'unreviewed_proposals' if result['available'] else 'no_usable_provider_result',
        'result':result,'accuracy_verified':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':record['status'],'attempts':result['attempts'],
        'elapsed_ms':record['elapsed_ms'],'classes':dict(Counter(o['device_class'] for o in result.get('proposed',[]))),
        'output':str(args.output)},ensure_ascii=True))


if __name__=='__main__':
    main()
