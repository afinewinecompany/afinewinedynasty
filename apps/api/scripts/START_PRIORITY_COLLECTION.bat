@echo off
echo ============================================================
echo STARTING PRIORITY PROSPECT DATA COLLECTION
echo ============================================================
echo.
echo This will collect play-by-play and pitch data for top prospects
echo Focusing on 2024-2025 seasons
echo.
echo Phase 1: Top 20 prospects with NO data
echo Phase 2: Top prospects needing PITCH data (#1 and #2 ranked!)
echo.

REM Activate virtual environment if needed
if exist "..\..\venv\Scripts\activate" (
    call ..\..\venv\Scripts\activate
)

REM Set Python path
set PYTHONPATH=%CD%\..

echo.
echo STARTING COLLECTION - Check logs for progress
echo.

REM Run the collection script
python run_priority_prospects_collection.py

echo.
echo ============================================================
echo COLLECTION COMPLETE - Check logs for results
echo ============================================================
pause