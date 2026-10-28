"""Opt-in editor live acceptance. Retains named review projects, removes temporary auth user."""
import copy,json,re,secrets,sys,uuid
from pathlib import Path
import httpx
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2]
if '--run-live' not in sys.argv: raise SystemExit('Use --run-live for acceptance writes.')
env=dotenv_values(ROOT/'backend/.env'); front=dotenv_values(ROOT/'.env.local')
base=env['SUPABASE_URL'].rstrip('/'); anon=front['VITE_SUPABASE_ANON_KEY']; service=env['SUPABASE_SERVICE_ROLE_KEY']
api='http://127.0.0.1:8000'; checks=[]; report={}; bid=None
admin={'apikey':service,'Authorization':'Bearer '+service}
def check(label,ok):
    assert ok,label
    checks.append(label); print('PASS: '+label,flush=True)
def login(email,password):
    r=httpx.post(base+'/auth/v1/token?grant_type=password',headers={'apikey':anon},json={'email':email,'password':password},timeout=30)
    check('Password session issued',r.status_code==200)
    return {'apikey':anon,'Authorization':'Bearer '+r.json()['access_token']}
def post(path,data,headers=None):
    return httpx.post(api+path,headers=headers or a,json=data,timeout=60)
def rows(table,**filters):
    r=httpx.get(base+'/rest/v1/'+table,headers=a,params={'select':'*',**filters},timeout=30)
    assert r.status_code==200
    return r.json()
def project(name,trade):
    r=httpx.post(base+'/rest/v1/projects',headers={**a,'Prefer':'return=representation'},json={'name':name,'description':'Task 7 live acceptance, retained for review','plan_type':trade,'status':'draft'},timeout=30)
    check('Review project created',r.status_code==201); return r.json()[0]['id']
def upload(pid,name):
    raw=(ROOT/'backend/tests/fixtures/plans'/name).read_bytes()
    r=httpx.post(api+f'/api/projects/{pid}/plans/{uuid.uuid4()}',headers=a,files={'file':(name,raw,'image/png')},timeout=60)
    check('Original uploaded',r.status_code==200);return r.json(),raw
def pre(rid):return {'expected_active_revision_id':rid,'idempotency_key':str(uuid.uuid4())}
try:
    lines=(ROOT/'passwords.md').read_text().splitlines(); idx=next(i for i,l in enumerate(lines) if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',l.strip()))
    a=login(lines[idx].strip(),next(l.strip() for l in lines[idx+1:] if l.strip()))
    previous_report=ROOT/'docs/supabase/EDITOR_LIVE_ACCEPTANCE_2026-10-11.json'
    prior=json.loads(previous_report.read_text()) if '--reuse-review-project' in sys.argv else {}
    pid=prior.get('review_project_id') or project('ACCEPTANCE R30 R31 EDITOR 2026-10-11','Floor Plan'); report['review_project_id']=pid
    prior_revision=rows('projects',id='eq.'+pid)[0]['active_revision_id']
    asset,raw=upload(pid,'01.png')
    r=httpx.post(api+'/api/estimate/image',headers=a,files={'file':('01.png',raw,'image/png')},data={'plan_type':'Floor Plan'},timeout=180)
    check('Real OCR completes',r.status_code==200); original=r.json()
    body={'project_id':pid,'precondition':pre(prior_revision),'result':original,'asset':{**{k:asset[k] for k in ('source_sha256','original_filename','media_type','byte_size')},'asset_id':asset['id']}}
    r=post('/api/estimate/revisions',body); check('Original revision saved',r.status_code==200); rid=r.json()['revision_id']
    rev=rows('estimate_revisions',id='eq.'+rid)[0]; sid=rev['scan_revision_id']; scan=rows('scan_revisions',id='eq.'+sid)[0]
    correction={'project_id':pid,'scan_revision_id':sid,'corrections':{'quantities':{'wall_height_m':3.2,'column_count':12,'slab_area_m2':80},'unit_prices':{'CHB02':0}}}
    r=post('/api/estimate/editor/preview',correction);check('Owned correction preview computes',r.status_code==200); preview=r.json()
    check('Preview leaves saved pointer unchanged',rows('projects',id='eq.'+pid)[0]['active_revision_id']==rid)
    saved={**correction,'precondition':pre(rid)}
    r=post('/api/estimate/editor/revisions',saved);check('Correction saved',r.status_code==200); corrected=r.json()['revision_id']
    check('Retry returns identical revision',post('/api/estimate/editor/revisions',saved).json()['revision_id']==corrected)
    stale={**saved,'precondition':pre(rid)};check('Stale save returns 409',post('/api/estimate/editor/revisions',stale).status_code==409)
    changed=copy.deepcopy(saved);changed['corrections']['unit_prices']['CHB02']=1
    check('Reused key with different edits refused',post('/api/estimate/editor/revisions',changed).status_code==409)
    current=rows('estimate_revisions',id='eq.'+corrected)[0]
    check('Reopened correction and prices match preview',current['effective_input']==preview['effective_input'] and current['corrections']==preview['corrections'])
    check('Reopened total matches preview',current['estimate']['grand_total']==preview['estimate']['grand_total'])
    check('Original scan remains immutable',rows('scan_revisions',id='eq.'+sid)[0]==scan)
    summary=rows('projects',id='eq.'+pid)[0]
    check('Compatibility summary matches active estimate',summary['grand_total']==current['estimate']['grand_total'] and summary['line_items']==current['estimate']['line_items'])
    email='trace-editor-'+uuid.uuid4().hex+'@example.invalid'; password=secrets.token_urlsafe(32)
    r=httpx.post(base+'/auth/v1/admin/users',headers=admin,json={'email':email,'password':password,'email_confirm':True},timeout=30)
    check('Temporary second user created',r.status_code in (200,201));bid=r.json()['id']; b=login(email,password)
    check('Foreign correction preview refused',post('/api/estimate/editor/preview',correction,b).status_code==404)
    check('Foreign correction save refused',post('/api/estimate/editor/revisions',saved,b).status_code==404)
    r=httpx.post(base+'/rest/v1/rpc/owned_estimate_scan',headers=a,json={'p_owner':bid,'p_project_id':pid,'p_scan_id':sid},timeout=30)
    check('Browser cannot invoke service-only source RPC',r.status_code in (401,403,404))
    reset={'project_id':pid,'scan_revision_id':sid,'corrections':{'quantities':{},'unit_prices':{}},'precondition':pre(corrected)}
    r=post('/api/estimate/editor/revisions',reset);check('Reset saved as new revision',r.status_code==200); resetid=r.json()['revision_id']
    check('Reset restores original amount',rows('estimate_revisions',id='eq.'+resetid)[0]['estimate']['grand_total']==original['estimate']['grand_total'])
    body['precondition']=pre(resetid)
    r=post('/api/estimate/revisions',body);check('Rescan creates new source revision',r.status_code==200);newid=r.json()['revision_id']
    fresh=rows('estimate_revisions',id='eq.'+newid)[0]
    check('Rescan keeps old source and clears corrections',fresh['scan_revision_id']!=sid and not fresh['corrections']['unit_prices'] and rows('scan_revisions',id='eq.'+sid)[0]==scan)
    mp=project('ACCEPTANCE R30 MANUAL REFUSED PLAN 2026-10-11','Floor Plan'); report['manual_project_id']=mp
    ma,mraw=upload(mp,'06.png')
    r=httpx.post(api+'/api/estimate/image',headers=a,files={'file':('06.png',mraw,'image/png')},data={'plan_type':'Floor Plan'},timeout=180)
    check('Known unreadable drawing still refused',r.status_code==422)
    check('Refusal recorded with original retained',post('/api/estimate/scan-failure',{'project_id':mp,'message':'The dimension chains do not close. Review the original and enter verified quantities manually.'}).status_code==200)
    manual={'project_id':mp,'asset_id':ma['id'],'inputs':{'confirmed':True,'width_m':10,'length_m':12,'exterior_wall_m':44,'interior_wall_m':20,'doors':4,'windows':5,'quantities':{'wall_height_m':2.7,'slab_area_m2':80,'column_count':12}}}
    r=post('/api/estimate/manual/preview',manual);check('Manual confirmed preview works after refusal',r.status_code==200)
    check('Foreign manual preview refused',post('/api/estimate/manual/preview',manual,b).status_code==404)
    # Leave the refused source for the browser manual-save check.
    report.update(status='passed',original_total=original['estimate']['grand_total'],corrected_total=current['estimate']['grand_total'],manual_preview_total=r.json()['estimate']['grand_total'],active_revision_id=newid)
finally:
    if bid:
        r=httpx.delete(base+'/auth/v1/admin/users/'+bid,headers=admin,timeout=30)
        check('Temporary second account removed',r.status_code in (200,204))
    report.update(checks_passed=len(checks),checks=checks)
    (ROOT/'docs/supabase/EDITOR_LIVE_ACCEPTANCE_2026-10-11.json').write_text(json.dumps(report,indent=2)+'\n')
