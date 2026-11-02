@echo off
rem Starts the backend (port 8000) and the frontend (port 5173) in two windows,
rem then opens the app. Close both windows to stop TRACE.
cd /d "%~dp0"

if not exist backend\.venv\Scripts\python.exe (
  echo Run setup.bat first.
  pause
  exit /b 1
)
if not exist node_modules (
  echo Run setup.bat first.
  pause
  exit /b 1
)

start "TRACE backend" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"
start "TRACE frontend" cmd /k "cd /d "%~dp0" && npm run dev"

echo Waiting for the servers to start...
timeout /t 8 /nobreak >nul
start "" http://localhost:5173
