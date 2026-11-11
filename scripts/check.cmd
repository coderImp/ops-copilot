@echo off
REM Pre-push quality gate: lint + tests + smoke eval.
REM Usage:  scripts\check.cmd            full check
REM         scripts\check.cmd quick      lint + tests only
REM Note: system `python` may be a Microsoft Store stub (hangs),
REM       so this script prefers the project-local .venv interpreter.

setlocal
cd /d "%~dp0.."

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY (
    where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [ERROR] no Python found. Run: uv sync --extra dev
    exit /b 1
)

echo == interpreter: %PY%
%PY% -c "import sys; print(sys.version.split()[0])"
if errorlevel 1 goto :fail

echo.
echo == lint (ruff)
%PY% -m ruff check .
if errorlevel 1 goto :fail

echo.
echo == unit tests (pytest)
%PY% -m pytest -q
if errorlevel 1 goto :fail

if /i "%~1"=="quick" goto :ok

echo.
echo == smoke: inject fault + run easy scenarios
%PY% -m sim.inject pool_exhaust >nul
if errorlevel 1 goto :fail
%PY% -m eval.run_eval --only easy | findstr /C:"task_success_rate" /C:"report ->"
if errorlevel 1 goto :fail

:ok
echo.
echo OK: all checks passed, safe to push.
exit /b 0

:fail
echo.
echo FAILED - fix the errors above before pushing.
exit /b 1
