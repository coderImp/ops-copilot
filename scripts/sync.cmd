@echo off
REM End-of-day sync: publish develop and fast-forward main WITHOUT switching branches.
REM
REM Why no "git checkout main": this .cmd lives in the repo, and checking out a
REM branch where it does not exist deletes it mid-execution
REM ("The batch file cannot be found.").
REM GitHub shows the default branch (main) on the repo home page, so run this
REM at the end of every day or the home page will show stale docs.
REM
REM Usage:  scripts\sync.cmd

setlocal
cd /d "%~dp0.."

REM Guard: refuse to run with uncommitted changes
for /f "usebackq delims=" %%i in (`git status --porcelain`) do (
    echo [ERROR] working tree is not clean:
    echo         %%i
    echo         commit your changes first, then run this again.
    exit /b 1
)

echo == current branch
set "CUR="
for /f "usebackq delims=" %%i in (`git rev-parse --abbrev-ref HEAD`) do set "CUR=%%i"
echo    %CUR%
if /i "%CUR%"=="main" (
    echo [ERROR] you are on main. "git branch -f main" cannot move the checked-out branch.
    echo         switch first:  git checkout develop
    exit /b 1
)

echo.
echo == push develop
git push
if errorlevel 1 exit /b 1

echo.
echo == move local main to develop
git branch -f main develop
if errorlevel 1 exit /b 1

echo.
echo == push develop to remote main (fast-forward only)
git push origin develop:main
if errorlevel 1 (
    echo [WARN] remote main rejected the update ^(not a fast-forward^).
    echo        Someone committed on main directly. Resolve manually.
    exit /b 1
)

echo.
echo == verify
git rev-list --count main..develop
echo ^(^"0^" above means main == develop^)

echo.
echo done. GitHub home page now shows the latest docs.
exit /b 0
