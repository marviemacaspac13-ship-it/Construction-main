# TRACE backend

FastAPI service that reads a construction plan image and returns a material estimate in
Philippine pesos, priced against the Supabase `materials` catalog. It reads a plan three
ways, depending on its type:

| Plan type | How it is read |
| --- | --- |
| Floor Plan | reads the printed dimensions (OCR), checks each dimension chain sums to its overall |
| Electrical Plan | matches drawn symbols against the reference crops in `templates/` |
| Plumbing Plan | reads the printed fixture tags (`WC`, `LAV`, `FD`) |

Everything after the reading is a deterministic rule engine (`app/takeoff/`). There is no
production fixture detector or YOLO route; the OCR engine (RapidOCR) ships inside its pip package, so
**nothing needs installing outside `pip`**.

Electrical symbol matching uses denoising and local contrast. Plumbing tag OCR and floor
dimension OCR decode the original pixels without that preprocessing. The [14 October
comparison](datasets/trade-preprocessing/RESULTS_2026-10-14.md) found that applying the
electrical preprocessor to the local plumbing/floor samples increased count or geometry
errors. The [electrical quality matrix](datasets/electrical-audit/QUALITY_MATRIX_2026-10-13.md)
records a separate native-versus-reduced-image experiment. Neither experiment supports
automatic upscaling or a general accuracy claim.

## 1. Install

Requires **Python 3.13**.

```bash
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt     # Windows
# .venv/bin/python -m pip install -r requirements.txt           # macOS / Linux
```

If pip fails on Windows with `No such file or directory ... numpy\f2py\...` and a hint about
**Long Path support**, the project folder is too deep. Move it somewhere short (e.g.
`C:\trace`) or enable long paths — the command is at the top of `requirements.txt` — then
delete the half-built `.venv` and install again.

## 2. Configure

Create `backend/.env` (it is gitignored, so it never comes with a clone):

```
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service role key>
```

Use the **service role** key (Project Settings → API), not the anon key; this runs
server-side. The backend reads the shared `materials` catalog and uses owner-checked
database functions for plan assets and estimate revisions. The service-role key must
never be sent to the browser. The browser uses its own session and anon key.

The frontend needs its own `.env.local` at the repository root with `VITE_SUPABASE_URL` and
`VITE_SUPABASE_ANON_KEY`.

`ESTIMATE_REVISIONS_ENABLED` and `PLAN_ASSETS_ENABLED` are separate backend feature flags;
leave them false until their migrations and deployment checks are complete. See
`.env.example` and the deployment notes below for the required order.

**Database setup.** Run the files in `../supabase/migrations/` in order, in the Supabase SQL
editor. `002_project_owner.sql` makes each project private to the account that created it;
later migrations add immutable revisions, private originals and source corrections. See the
[revision](../docs/supabase/REVISION_DEPLOYMENT.md), [plan-asset](../docs/supabase/PLAN_ASSET_DEPLOYMENT.md)
and [editor](../docs/supabase/EDITOR_DEPLOYMENT.md) deployment notes before enabling those features.

## 3. Run

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Check it is alive: http://localhost:8000/health

**Every other route needs a signed-in user.** The browser sends its Supabase session as
`Authorization: Bearer <access token>`, and `app/auth.py` checks it with Supabase. A request
without one gets a 401. Restart the server after editing the `materials` table — the catalog
is cached.

## 4. Test

```bash
.venv\Scripts\python.exe -m pytest -q                 # everything, ~3 min
.venv\Scripts\python.exe -m pytest -q -m "not ocr"    # skip the slow image tests, ~5 s
```

The tests run offline: prices come from a committed catalog snapshot, and the API tests act
as a stand-in signed-in user (`tests/conftest.py`).

The complete run on 14 October 2026 passed **606 tests** with four dependency deprecation
warnings. The frontend's three Node test files passed **28 tests**, and `npm run typecheck`
passed. These are software checks, not independent recognition validation.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | liveness, no login needed |
| POST | `/api/estimate/image` | multipart `file` + `plan_type`, optionally floor-plan `wall_height_m` → priced estimate and replayable input snapshot. **What the app uses.** |
| POST | `/api/estimate` | a `PlanSchema` as JSON → priced estimate |
| POST | `/api/estimate/recalculate` | recompute supported quantity and project-price corrections from a saved input snapshot |
| POST | `/api/estimate/revisions` | atomically save an immutable estimate revision |
| POST | `/api/projects/{project_id}/plans/{upload_id}` | save the private original image |
| GET | `/api/projects/{project_id}/plans/{asset_id}/view` | issue a short-lived authorized viewing link |
| GET | `/api/materials` | the catalog |
| GET / POST | `/api/templates` | list / upload symbol reference crops |
| DELETE | `/api/templates/{item_id}/{filename}` | remove a crop |
| POST | `/api/scan` | older symbol-count endpoint; unused by the app |

The current `/api/estimate/image` path refuses a plan it cannot read with a **422 and the
reason**, rather than pricing a handful of stray matches. The older `/api/scan` route is
retained for compatibility and is not used by the app.

Plan-image uploads accept static PNG, JPEG or WebP images with matching MIME and decoded
format. The saved-original, direct scan and image-estimate routes limit files to 25 MB and
40 million pixels. The upload screen's readability guidance is coordinated with the
coworker's UI work. A file passing format limits is not necessarily legible enough for OCR.

## Where the numbers come from

Quantities follow `Guide.docx` (the project standard) and named Philippine references — the
NSCP, the PEC, the NBCP, Fajardo. Anything not on the drawing is stated as an assumption on
every estimate and logged to `runs/estimates.jsonl`. See `app/takeoff/params.py` for each
value and its source.
