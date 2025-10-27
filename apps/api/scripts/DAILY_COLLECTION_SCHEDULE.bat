@echo off
REM ============================================================
REM DAILY AUTOMATED COLLECTION FOR MLB PROSPECTS
REM Schedule this to run at 3 AM daily using Windows Task Scheduler
REM ============================================================

echo ============================================================
echo DAILY PROSPECT DATA COLLECTION
echo Started: %date% %time%
echo ============================================================

REM Navigate to scripts directory
cd /d "C:\Users\lilra\myprojects\afinewinedynasty\apps\api\scripts"

REM Log file with date
set LOGFILE=daily_collection_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log

echo.
echo Phase 1: Collecting new games for existing prospects...
python collect_new_games.py >> %LOGFILE% 2>&1

echo.
echo Phase 2: Collecting pitch data for games with PBP only...
python collect_missing_pitches.py >> %LOGFILE% 2>&1

echo.
echo Phase 3: Checking for new prospects...
python check_new_prospects.py >> %LOGFILE% 2>&1

echo.
echo ============================================================
echo COLLECTION COMPLETE
echo Ended: %date% %time%
echo Log saved to: %LOGFILE%
echo ============================================================

REM Keep window open for 10 seconds to see results
timeout /t 10