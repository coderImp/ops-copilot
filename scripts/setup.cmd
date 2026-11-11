@echo off
REM One-time setup: sync the project .venv and install dev deps via uv.
REM Usage:  scripts\setup.cmd

setlocal
cd /d "%~dp0.."

where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv not found. Install: winget install astral-sh.uv
    exit /b 1
)

echo == uv sync (dev extras)
uv sync --extra dev
if errorlevel 1 exit /b 1

echo.
echo == verify
".venv\Scripts\python.exe" -c "import sys; print(sys.version.split()[0])"
".venv\Scripts\python.exe" -m ruff --version
".venv\Scripts\python.exe" -m pytest --version

echo.
echo done. Next: scripts\check.cmd
echo daily: .venv\Scripts\python.exe -m eval.run_eval --planner llm
exit /b 0
