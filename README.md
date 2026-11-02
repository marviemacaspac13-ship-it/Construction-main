# TRACE

TRACE reads construction plan images and produces material estimates in Philippine pesos. A Vite frontend handles sign-in, projects and saved results through Supabase. A FastAPI service in `backend/` reads drawings and calculates estimates.

## Running it (Windows)

1. Install **Python 3.13** (`winget install --id Python.Python.3.13`) and **Node.js** (https://nodejs.org).
2. Unzip to a short folder such as `C:\TRACE`. A deeply nested folder can break the Python install on Windows (path-length limit).
3. Double-click **`setup.bat`** once. It installs everything (a few minutes, ~1 GB).
4. Double-click **`start.bat`**. It opens two server windows and the app at http://localhost:5173. Close both windows to stop.

The sign-in for testing is in `passwords.md`. The Supabase keys are already in `.env.local` (frontend) and `backend/.env` (backend).

**Note:** `backend/.env` has Gemini switched on, so scanning an electrical or plumbing plan uploads the drawing to Google. Set `PLUMBING_VISION_ENABLED=false` and `ELECTRICAL_VISION_ENABLED=false` in `backend/.env` to keep scans local.

## Manual commands

```
npm run dev                                                    # frontend, from this folder
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000   # backend
.venv\Scripts\python.exe -m pytest -q -m "not ocr"             # backend tests
```

More on the backend and its API is in [backend/README.md](backend/README.md).

## Sample plans

`sample-plans/` has five drawings to try: a floor plan that reads cleanly, an electrical lighting plan, a plumbing plan, a floor plan the app deliberately refuses (metre scale), and a colour electrical layout with lights, outlets and switches. Create a project with the matching plan type and upload one. More are in `backend/tests/fixtures/plans/`.
