@echo off
REM Restart the PR Card Watchdog if it died
REM Run this after machine reboot or if watchdog_status.json shows stale timestamps

cd /d "%~dp0"

REM Kill any existing watchdog
taskkill /F /FI "WINDOWTITLE eq watchdog_run*" >nul 2>&1

echo Starting PR Card watchdog...
start /B "watchdog_run" .venv\Scripts\python.exe watchdog_run.py >> outputs\watchdog_stdout.txt 2>&1

echo Watchdog launched. Check outputs\watchdog_status.json for progress.
echo The watchdog polls every 5 minutes and auto-scrapes when Mahabhumi comes back.
pause
