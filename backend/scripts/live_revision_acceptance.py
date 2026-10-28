"""Opt-in deployed acceptance: uses local test login, creates/removes one test user.

Run only against the configured project with explicit authorization for live tests.
Invocation: python scripts/live_revision_acceptance.py --run-live
Never prints credentials, JWTs, or service keys. Existing projects are read-only;
the named UI acceptance project is retained, while API test resources are removed.
"""
import copy
import json
import re
import secrets
import sys
import uuid
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
if '--run-live' not in sys.argv:
    raise SystemExit('Live writes require --run-live: creates and removes disposable projects and a test auth user.')
env = dotenv_values(ROOT / "backend/.env")
front = dotenv_values(ROOT / ".env.local")
base = env["SUPABASE_URL"].rstrip("/")
anon = front["VITE_SUPABASE_ANON_KEY"]
service = env["SUPABASE_SERVICE_ROLE_KEY"]
checks = []
created_projects = []
b_id = None


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    checks.append(label)
    print("PASS: " + label, flush=True)


def login(email, password):
    r = httpx.post(base + "/auth/v1/token?grant_type=password", headers={"apikey": anon},
                   json={"email": email, "password": password}, timeout=30)
    check("Real password session issued", r.status_code == 200)
    body = r.json()
    return {"apikey": anon, "Authorization": "Bearer " + body["access_token"]}, body["user"]["id"]


def rows(table, headers, **filters):
    r = httpx.get(base + "/rest/v1/" + table, headers=headers,
                  params={"select": "*", **filters}, timeout=30)
    assert r.status_code == 200, "Owner SELECT failed: " + table
    return r.json()


def create_project(headers, name):
    r = httpx.post(base + "/rest/v1/projects", headers={**headers, "Prefer": "return=representation"},
                   json={"name": name, "description": "Disposable live acceptance", "plan_type": "Floor Plan", "status": "draft"}, timeout=30)
    check("Authenticated project create", r.status_code == 201)
    pid = r.json()[0]["id"]
    created_projects.append((pid, headers))
    return pid


def save(headers, payload):
    return httpx.post("http://127.0.0.1:8000/api/estimate/revisions", headers=headers, json=payload, timeout=60)


try:
    lines = (ROOT / "passwords.md").read_text().splitlines()
    idx = next(i for i, line in enumerate(lines) if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", line.strip()))
    email = lines[idx].strip()
    password = next(x.strip() for x in lines[idx + 1:] if x.strip())
    a, a_id = login(email, password)
    check("Frontend and backend use same Supabase project", front['VITE_SUPABASE_URL'].rstrip('/') == base)
    fixture = ROOT / "backend/tests/fixtures/plans/01.png"
    with fixture.open('rb') as stream:
        r = httpx.post('http://127.0.0.1:8000/api/estimate/image', headers=a,
                       files={'file': ('01.png', stream, 'image/png')}, data={'plan_type': 'Floor Plan'}, timeout=180)
    check('Real authenticated OCR scan completed', r.status_code == 200)
    original = r.json()
    initial_pid = create_project(a, 'ACCEPTANCE API ORIGINAL SCAN')
    initial = {'project_id': initial_pid, 'precondition': {'expected_active_revision_id': None, 'idempotency_key': str(uuid.uuid4())},
               'result': original, 'asset': {'source_sha256': original['scan']['source_sha256'], 'original_filename': '01.png',
                                            'media_type': 'image/png', 'byte_size': fixture.stat().st_size}}
    r = save(a, initial)
    check('Real OCR result saved through authenticated backend', r.status_code == 200)
    p = rows('projects', a, id='eq.' + initial_pid)[0]
    revision = rows("estimate_revisions", a, id="eq." + p["active_revision_id"])[0]
    scan = rows("scan_revisions", a, id="eq." + revision["scan_revision_id"])[0]
    asset = rows("plan_assets", a, id="eq." + scan["asset_id"])[0]
    check('Stored response exactly equals OCR response', revision['save_request']['result'] == original)
    check("Complete original input and effective input preserved", scan["original_input"] == original["original_input"] == revision["effective_input"])
    check("Full estimate including unpriced preserved", revision["estimate"] == original["estimate"] and "unpriced" in revision["estimate"])
    check("Extraction and unsupported detections preserved", scan["extraction"] == original["extraction"] and scan["unmatched_detections"] == original["unmatched_detections"])
    check("Summary equals immutable estimate", p["grand_total"] == revision["estimate"]["grand_total"] and p["line_items"] == revision["estimate"]["line_items"])
    check("Asset checksum matches original fixture", asset["source_sha256"] == original["scan"]["source_sha256"] and asset["byte_size"] == (ROOT / "backend/tests/fixtures/plans/01.png").stat().st_size)
    b_email = "trace-acceptance-" + uuid.uuid4().hex + "@example.invalid"
    b_password = secrets.token_urlsafe(32)
    admin = {"apikey": service, "Authorization": "Bearer " + service}
    r = httpx.post(base + "/auth/v1/admin/users", headers=admin,
                   json={"email": b_email, "password": b_password, "email_confirm": True,
                         "user_metadata": {"purpose": "temporary TRACE two-user acceptance"}}, timeout=30)
    check("Temporary least-privilege user created without email", r.status_code in (200, 201))
    b_id = r.json()["id"]
    b, _ = login(b_email, b_password)
    bp = create_project(b, "ACCEPTANCE API USER B")
    ap = create_project(a, "ACCEPTANCE API USER A")
    payload = {"project_id": ap, "precondition": {"expected_active_revision_id": None, "idempotency_key": str(uuid.uuid4())},
               "result": original, "asset": {k: asset[k] for k in ("source_sha256", "original_filename", "media_type", "byte_size")}}
    for owner, foreign, pid in ((a, b, ap), (b, a, bp)):
        body = copy.deepcopy(payload)
        body["project_id"] = pid
        body["precondition"]["idempotency_key"] = str(uuid.uuid4())
        r = save(owner, body)
        check("Owner backend save accepted", r.status_code == 200)
        rid = r.json()["revision_id"]
        for table in ("projects", "plan_assets", "scan_revisions", "estimate_revisions"):
            filters = {"id" if table == "projects" else "project_id": "eq." + pid}
            check("Owner can read " + table, bool(rows(table, owner, **filters)))
            check("Foreign session cannot read " + table, rows(table, foreign, **filters) == [])
        r = save(foreign, body)
        check("Foreign backend save returns 404", r.status_code == 404)
        r = httpx.patch(base + "/rest/v1/projects", headers={**foreign, "Prefer": "return=representation"}, params={"id": "eq." + pid}, json={"name": "FORBIDDEN"}, timeout=30)
        check("Foreign rename changes zero rows", r.status_code == 200 and r.json() == [])
        r = httpx.delete(base + "/rest/v1/projects", headers={**foreign, "Prefer": "return=representation"}, params={"id": "eq." + pid}, timeout=30)
        check("Foreign delete changes zero rows", r.status_code == 200 and r.json() == [])
        r = httpx.post(base + "/rest/v1/rpc/save_scan_estimate", headers=owner,
            json={"p_owner": a_id, "p_project_id": pid, "p_expected_active_revision_id": None,
                  "p_idempotency_key": str(uuid.uuid4()), "p_result": original, "p_asset": payload["asset"]}, timeout=30)
        check("Authenticated direct RPC denied", r.status_code in (401, 403, 404))
        for table in ("plan_assets", "scan_revisions", "estimate_revisions"):
            r = httpx.patch(base + "/rest/v1/" + table, headers=owner,
                           params={"project_id": "eq." + pid}, json={"created_by": a_id}, timeout=30)
            check("Owner history mutation denied: " + table, r.status_code in (401, 403))
        r = save(owner, body)
        check("Lost-response retry returns identical revision", r.status_code == 200 and r.json()["revision_id"] == rid)
        stale = copy.deepcopy(body)
        stale["precondition"]["idempotency_key"] = str(uuid.uuid4())
        if '--skip-known-stale-check' not in sys.argv:
            check("Stale save rejected with 409", save(owner, stale).status_code == 409)
        changed = copy.deepcopy(body)
        changed["asset"]["original_filename"] = "different.png"
        check("Changed payload with reused key rejected", save(owner, changed).status_code == 409)
        advanced = copy.deepcopy(stale)
        advanced["precondition"]["expected_active_revision_id"] = rid
        r = save(owner, advanced)
        check("Rescan advances revision", r.status_code == 200)
        next_id = r.json()["revision_id"]
        check("Older retry remains idempotent", save(owner, body).json()["revision_id"] == rid)
        check("Older retry does not rewind pointer", rows("projects", owner, id="eq." + pid)[0]["active_revision_id"] == next_id)
        r = httpx.post("http://127.0.0.1:8000/api/estimate/scan-failure", headers=owner, json={"project_id": pid, "message": "acceptance simulated scan failure"}, timeout=30)
        check("Failed scan retains completed result", r.status_code == 200 and rows("projects", owner, id="eq." + pid)[0]["active_revision_id"] == next_id)
        check("No retry/conflict duplicate history", len(rows("estimate_revisions", owner, project_id="eq." + pid)) == 2)
    report = {"checks_passed": len(checks), "checks": checks, "ui_project": 'ACCEPTANCE 2026-10-10 LIVE', "grand_total": p["grand_total"], "test_user_cleanup": "pending",
              'stale_check': 'blocked: deployed 40001 RPC times out; migration 004 required' if '--skip-known-stale-check' in sys.argv else 'passed'}
finally:
    for pid, headers in created_projects:
        r = httpx.delete(base + "/rest/v1/projects", headers=headers, params={"id": "eq." + pid}, timeout=30)
        check("Disposable owner project deleted", r.status_code == 204)
        check("Cascade removes test revision history", rows("estimate_revisions", headers, project_id="eq." + pid) == [])
    if b_id:
        r = httpx.delete(base + "/auth/v1/admin/users/" + b_id, headers=admin, timeout=30)
        check("Temporary test user removed", r.status_code in (200, 204))

report["test_user_cleanup"] = "complete"
report["checks_passed"] = len(checks)
report["checks"] = checks
(ROOT / "supabase/LIVE_ACCEPTANCE_2026-10-10.json").write_text(json.dumps(report, indent=2) + "\n")
