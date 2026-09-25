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
trained model and no YOLO; the OCR engine (RapidOCR) ships inside its pip package, so
**nothing needs installing outside `pip`**.

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
server-side. The backend uses it only to read the shared `materials` catalog — it never
reads or writes projects.

The frontend needs its own `.env.local` at the repository root with `VITE_SUPABASE_URL` and
`VITE_SUPABASE_ANON_KEY`.

**Database setup.** Run the files in `../supabase/migrations/` in order, in the Supabase SQL
editor. `002_project_owner.sql` makes each project private to the account that created it.

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

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | liveness, no login needed |
| POST | `/api/estimate/image` | multipart `file` + `plan_type` → priced estimate. **What the app uses.** |
| POST | `/api/estimate` | a `PlanSchema` as JSON → priced estimate |
| GET | `/api/materials` | the catalog |
| GET / POST | `/api/templates` | list / upload symbol reference crops |
| DELETE | `/api/templates/{item_id}/{filename}` | remove a crop |
| POST | `/api/scan` | older symbol-count endpoint; unused by the app |

A plan TRACE cannot read is refused with a **422 and the reason** — never priced at zero or
from a handful of stray matches.

## Where the numbers come from

Quantities follow `Guide.docx` (the project standard) and named Philippine references — the
NSCP, the PEC, the NBCP, Fajardo. Anything not on the drawing is stated as an assumption on
every estimate and logged to `runs/estimates.jsonl`. See `app/takeoff/params.py` for each
value and its source.
