@echo off
REM Windows batch script to run pitch data audit
REM Can be scheduled via Windows Task Scheduler

echo ========================================
echo Running Pitch Data Audit
echo ========================================
echo.

REM Navigate to the API directory
cd /d "C:\Users\lilra\myprojects\afinewinedynasty\apps\api"

REM Run the audit
python scheduled_pitch_audit.py --output ./audit_reports

REM Check if audit found issues
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARNING] Audit reported issues. Check the reports.

    REM Optionally trigger collection
    REM python collect_missing_pitches_final.py
) else (
    echo.
    echo [OK] Audit completed successfully.
)

echo.
echo Audit complete at %date% %time%
echo ========================================