@echo off
REM ── Sam Launcher ──────────────────────────────────────────────
REM Double-click this file to put the floating SAM button on screen.
REM The launcher stays on top of all windows; click the orb to start Sam.

cd /d "%~dp0"

REM Use explicit Python 3.13 path so the correct installation is always used
REM (avoids Windows Store stub pythonw.exe that appears first on PATH)
if exist "C:\Python313\pythonw.exe" (
    start "" "C:\Python313\pythonw.exe" "%~dp0launcher.py"
) else if exist "C:\Python313\python.exe" (
    start "" "C:\Python313\python.exe" "%~dp0launcher.py"
) else (
    REM Final fallback — use whatever pythonw is on PATH
    start "" pythonw "%~dp0launcher.py"
)
