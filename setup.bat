@echo off
rem One-time install: Python packages for the backend, Node packages for the frontend.
rem Needs Python 3.13 and Node.js (18 or newer) installed first.
setlocal
cd /d "%~dp0"

where npm >nul 2>nul
if errorlevel 1 (
  echo Node.js is not installed. Get it from https://nodejs.org and run setup.bat again.
  pause
  exit /b 1
)

set "PY="
py -3.13 --version >nul 2>nul && set "PY=py -3.13"
if not defined PY (
  python --version 2>nul | findstr /b /c:"Python 3.13" >nul && set "PY=python"
)
if not defined PY (
  echo Python 3.13 is not installed. Install it with:
  echo   winget install --id Python.Python.3.13
  echo then run setup.bat again.
  pause
  exit /b 1
)

echo.
echo === Backend: creating backend\.venv with %PY% ===
if not exist backend\.venv\Scripts\python.exe (
  %PY% -m venv backend\.venv || goto :fail
)
backend\.venv\Scripts\python.exe -m pip install --upgrade pip || goto :fail
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt || goto :pipfail

echo.
echo === Frontend: installing Node packages ===
call npm ci || goto :fail

echo.
echo Setup finished. Run start.bat to open TRACE.
pause
exit /b 0

:pipfail
echo.
echo The Python install failed. If the error mentions "No such file or directory"
echo or Long Path support, move this folder somewhere short (for example C:\TRACE),
echo delete backend\.venv, and run setup.bat again.
pause
exit /b 1

:fail
echo.
echo Setup failed - see the error above.
pause
exit /b 1
