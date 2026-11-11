@echo off
REM End-of-day sync: fast-forward main to develop and push.
REM GitHub shows the default branch (main) on the repo home page, so run this
REM at the end of every day or the home page will show stale docs.
REM Usage:  scripts\sync.cmd

setlocal
cd /d "%~dp0.."

REM Guard: refuse to run with uncommitted changes (git pull/merge would abort confusingly)
for /f "usebackq delims=" %%i in (`git status --porcelain`) do (
    echo [ERROR] working tree is not clean:
    echo         %%i
    echo         commit your changes first, then run this again.
    exit /b 1
)

echo == pull latest develop
git checkout develop
if errorlevel 1 exit /b 1
git pull --rebase
if errorlevel 1 exit /b 1

echo.
echo == fast-forward main
git checkout main
if errorlevel 1 exit /b 1
git merge --ff-only develop
if errorlevel 1 (
    echo [WARN] main cannot fast-forward. Resolve manually:
    echo        git merge develop
    exit /b 1
)

echo.
echo == push
git push
if errorlevel 1 exit /b 1

echo.
echo == back to develop
git checkout develop
echo done. main == develop, GitHub home page now up to date.
exit /b 0
