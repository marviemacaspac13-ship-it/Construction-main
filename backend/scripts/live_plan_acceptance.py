"""Opt-in live R32 checks; keeps one clearly named owner-A review project.

Uses local test credentials without logging secrets. Creates/removes disposable
projects and one test user. Invocation: python scripts/live_plan_acceptance.py --run-live
"""
import hashlib
import io
import json
import re
import secrets
import sys
import time
import uuid
from pathlib import Path

import httpx
from dotenv import dotenv_values
from PIL import Image

if '--run-live' not in sys.argv:
    raise SystemExit('Requires --run-live for disposable live writes.')
ROOT = Path(__file__).resolve().parents[2]
env = dotenv_values(ROOT / 'backend/.env')
front = dotenv_values(ROOT / '.env.local')
base = env['SUPABASE_URL'].rstrip('/')
anon = front['VITE_SUPABASE_ANON_KEY']
service = env['SUPABASE_SERVICE_ROLE_KEY']
admin = {'apikey': service, 'Authorization': 'Bearer ' + service}
api = 'http://127.0.0.1:8000'
checks, disposable, stored = [], [], []
b_id = None
report = {'live_storage': 'in progress'}
report_path = ROOT / 'docs/supabase/PLAN_ASSET_LIVE_ACCEPTANCE_2026-10-11.json'


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    checks.append(label)
    print('PASS: ' + label, flush=True)


def record():
    report.update(checks_passed=len(checks), checks=checks)
    report_path.write_text(json.dumps(report, indent=2) + '\n')


def login(email, password):
    r = httpx.post(base + '/auth/v1/token?grant_type=password', headers={'apikey': anon},
                   json={'email': email, 'password': password}, timeout=30)
    check('Authenticated password session', r.status_code == 200)
    return {'apikey': anon, 'Authorization': 'Bearer ' + r.json()['access_token']}, r.json()['user']['id']


def project(headers, name, retain=False):
    r = httpx.post(base + '/rest/v1/projects', headers={**headers, 'Prefer': 'return=representation'},
                   json={'name': name, 'plan_type': 'Floor Plan', 'status': 'draft',
                         'description': 'R32 live acceptance; real fixture, test project'}, timeout=30)
    check('Owner creates acceptance project', r.status_code == 201)
    pid = r.json()[0]['id']
    if not retain:
        disposable.append((pid, headers))
    return pid


def rows(table, headers, **filters):
    r = httpx.get(base + '/rest/v1/' + table, headers=headers, params={'select': '*', **filters}, timeout=30)
    check('Authorized table query: ' + table, r.status_code == 200)
    return r.json()


def upload(headers, pid, uid, raw, name='01.png'):
    return httpx.post(f'{api}/api/projects/{pid}/plans/{uid}', headers=headers,
                      files={'file': (name, raw, 'image/png')}, timeout=60)


def view(headers, pid, asset):
    return httpx.get(f'{api}/api/projects/{pid}/plans/{asset}/view', headers=headers, timeout=30)


try:
    lines = (ROOT / 'passwords.md').read_text().splitlines()
    idx = next(i for i, line in enumerate(lines) if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', line.strip()))
    a, a_id = login(lines[idx].strip(), next(x.strip() for x in lines[idx+1:] if x.strip()))
    b_email, b_password = 'trace-r32-' + uuid.uuid4().hex + '@example.invalid', secrets.token_urlsafe(32)
    r = httpx.post(base + '/auth/v1/admin/users', headers=admin,
                   json={'email': b_email, 'password': b_password, 'email_confirm': True}, timeout=30)
    check('Disposable second account created without email delivery', r.status_code in (200,201))
    b_id = r.json()['id']
    b, _ = login(b_email,b_password)
    if '--reuse-review-project' in sys.argv:
        ap = json.loads(report_path.read_text())['review_project_id']
    else:
        ap = project(a, 'ACCEPTANCE R32 ORIGINAL PLAN 2026-10-11', retain=True)
    previous_revision = rows('projects',a,id='eq.'+ap)[0]['active_revision_id']
    bp = project(b, 'DISPOSABLE R32 USER B')
    report['review_project_id'] = ap
    raw = (ROOT / 'backend/tests/fixtures/plans/01.png').read_bytes()
    a_asset = None
    for owner, foreign, pid, owner_id in ((a,b,ap,a_id),(b,a,bp,b_id)):
        uid = str(uuid.uuid4())
        r = upload(owner,pid,uid,raw)
        check('Owner uploads original through authenticated API', r.status_code == 200)
        asset = r.json()
        if pid == bp:
            stored.append(asset['storage_path'])
        check('Original SHA, bytes and dimensions retained', asset['source_sha256'] == hashlib.sha256(raw).hexdigest()
              and asset['byte_size'] == len(raw) and asset['pixel_width'] > 0 and asset['pixel_height'] > 0)
        r = upload(owner,pid,uid,raw)
        check('Lost-response upload retry returns same immutable ID', r.status_code == 200 and r.json()['id'] == asset['id'])
        check('Changed content with same upload ID rejected', upload(owner,pid,uid,raw,name='changed.png').status_code == 409)
        check('Foreign upload refused before object operation', upload(foreign,pid,str(uuid.uuid4()),raw).status_code == 404)
        check('Foreign viewing request refused', view(foreign,pid,asset['id']).status_code == 404)
        check('Foreign asset table query empty', rows('plan_assets',foreign,project_id='eq.'+pid) == [])
        path = asset['storage_path']
        for session in (owner,foreign,{'apikey':anon}):
            r = httpx.get(base+'/storage/v1/object/authenticated/trace-plans/'+path,headers=session,timeout=30)
            check('Direct browser-role private-object read refused', r.status_code != 200)
        r = httpx.post(base+'/storage/v1/object/trace-plans/'+owner_id+'/'+pid+'/'+str(uuid.uuid4())+'/original.png',
                       headers={**owner,'Content-Type':'image/png'},content=raw,timeout=30)
        check('Direct browser-role object upload refused', r.status_code not in (200,201))
        r = view(owner,pid,asset['id'])
        check('Owner receives five-minute link', r.status_code == 200 and r.json()['expires_in'] == 300)
        link = r.json()['url']
        check('Signed link returns exact original bytes', httpx.get(link,timeout=30).content == raw)
        if pid == ap:
            a_asset = asset
            old_link, old_link_time = link, time.monotonic()
        check('Cleanup preserves ready original', httpx.post(api+'/api/plans/cleanup',headers=owner,timeout=30).status_code == 200
              and view(owner,pid,asset['id']).status_code == 200)
    r = httpx.post(api+'/api/estimate/image',headers=a,files={'file':('01.png',raw,'image/png')},
                   data={'plan_type':'Floor Plan'},timeout=180)
    check('Real floor-plan OCR scan completes', r.status_code == 200)
    original = r.json()
    body = {'project_id':ap,'precondition':{'expected_active_revision_id':previous_revision,'idempotency_key':str(uuid.uuid4())},
            'result':original,'asset':{**{k:a_asset[k] for k in ('source_sha256','original_filename','media_type','byte_size')},'asset_id':a_asset['id']}}
    r = httpx.post(api+'/api/estimate/revisions',headers=a,json=body,timeout=60)
    check('Real result saved with uploaded immutable asset',r.status_code == 200)
    rid = r.json()['revision_id']
    check('Lost-save retry retains revision',httpx.post(api+'/api/estimate/revisions',headers=a,json=body,timeout=60).json()['revision_id'] == rid)
    revision = rows('estimate_revisions',a,id='eq.'+rid)[0]
    scan = rows('scan_revisions',a,id='eq.'+revision['scan_revision_id'])[0]
    check('Reopened revision references exact original',scan['asset_id'] == a_asset['id'])
    check('Summary uses same active revision',rows('projects',a,id='eq.'+ap)[0]['active_revision_id'] == rid)
    report.update(grand_total=original['estimate']['grand_total'],scan_revision_id=scan['id'],asset_id=a_asset['id'])
    second = upload(a,ap,str(uuid.uuid4()),raw,name='replacement.png')
    check('Replacement creates separate original',second.status_code == 200 and second.json()['id'] != a_asset['id'])
    check('Replacement does not change active scan image',rows('scan_revisions',a,id='eq.'+scan['id'])[0]['asset_id'] == a_asset['id'])
    fail_pid = project(a,'DISPOSABLE R32 REFUSED SCAN')
    buffer = io.BytesIO(); Image.new('RGB',(128,128),'white').save(buffer,format='PNG')
    blank = buffer.getvalue()
    r = upload(a,fail_pid,str(uuid.uuid4()),blank,name='unreadable.png')
    check('Original retained before refused scan',r.status_code == 200)
    refused_asset = r.json(); stored.append(refused_asset['storage_path'])
    r = httpx.post(api+'/api/estimate/image',headers=a,files={'file':('unreadable.png',blank,'image/png')},data={'plan_type':'Floor Plan'},timeout=180)
    check('Unreadable plan correctly refused',r.status_code in (400,422))
    r = httpx.post(api+'/api/estimate/scan-failure',headers=a,json={'project_id':fail_pid,'message':'Live acceptance: unreadable image'},timeout=30)
    check('Failed first scan records refusal',r.status_code == 200)
    check('Failed first scan original remains viewable',view(a,fail_pid,refused_asset['id']).status_code == 200)
    r = httpx.post(api+'/api/estimate/scan-failure',headers=a,json={'project_id':ap,'message':'Live acceptance: refused rescan'},timeout=30)
    check('Refused rescan preserves completed revision',r.status_code == 200 and rows('projects',a,id='eq.'+ap)[0]['active_revision_id'] == rid)
    report['live_storage'] = 'expiry check pending'; record()
    while time.monotonic()-old_link_time < 310:
        time.sleep(min(30,max(1,310-(time.monotonic()-old_link_time))))
        print('Waiting for original five-minute capability to expire.',flush=True)
    check('Actual original five-minute link expires',httpx.get(old_link,timeout=30).status_code != 200)
    r = view(a,ap,a_asset['id'])
    check('New authorized link works after expiry',r.status_code == 200 and httpx.get(r.json()['url'],timeout=30).content == raw)
    report['live_storage'] = 'passed'
except Exception as exc:
    report['live_storage'] = 'failed'
    report['failure_type'] = type(exc).__name__
    raise
finally:
    for pid,headers in disposable:
        r = httpx.delete(base+'/rest/v1/projects',headers=headers,params={'id':'eq.'+pid},timeout=30)
        check('Disposable project removed',r.status_code == 204)
    for path in stored:
        r = httpx.request('DELETE',base+'/storage/v1/object/trace-plans',headers=admin,json={'prefixes':[path]},timeout=30)
        check('Disposable test original removed',r.status_code in (200,204))
        owner_id = path.split('/')[0]
        r = httpx.post(base+'/rest/v1/rpc/finish_plan_file_cleanup',headers=admin,json={'p_owner':owner_id,'p_path':path},timeout=30)
        check('Disposable cleanup queue acknowledged',r.status_code in (200,204))
    if b_id:
        r = httpx.delete(base+'/auth/v1/admin/users/'+b_id,headers=admin,timeout=30)
        check('Disposable second account removed',r.status_code in (200,204))
    report['disposable_cleanup'] = 'complete'
    record()
