@echo off
REM Batch file to start collections and prevent Windows sleep
REM Run as Administrator for best results

echo ========================================
echo MLB Collections - No Sleep Mode
echo ========================================
echo.

REM Check if running as admin
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo WARNING: Not running as Administrator!
    echo Some features may not work properly.
    echo Right-click and select "Run as Administrator" for best results.
    echo.
    pause
)

echo Starting collections with sleep prevention...
echo.

REM Method 1: Use caffeine-like behavior with Python
echo Option 1: Python Keep-Awake Collector
echo This will run collections and prevent sleep
echo.

cd /d "%~dp0\.."
python scripts\keep_awake_collector.py --collection-type all --years 2023 2024 2025

echo.
echo Collections complete or stopped by user.
echo.

REM Alternative: Use PowerShell method
echo If the above didn't work, you can also:
echo 1. Open PowerShell as Administrator
echo 2. Navigate to: %~dp0
echo 3. Run: .\prevent_sleep.ps1
echo 4. When done, run: .\restore_sleep.ps1
echo.

pause