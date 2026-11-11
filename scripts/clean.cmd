@echo off
REM Clean local runtime artifacts (never touches source or git history).
REM Usage:  scripts\clean.cmd

setlocal
cd /d "%~dp0.."

if exist data rmdir /s /q data 2>nul & echo removed data\
for /d %%d in (opscop-*) do rmdir /s /q "%%d" 2>nul & echo removed %%d\
if exist eval\eval_report.md del /q eval\eval_report.md 2>nul & echo removed eval\eval_report.md

for /d /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
if exist .pytest_cache rmdir /s /q .pytest_cache 2>nul
if exist .ruff_cache rmdir /s /q .ruff_cache 2>nul

echo.
echo clean done.
exit /b 0
