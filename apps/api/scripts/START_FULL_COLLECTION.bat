@echo off
echo ================================================================================
echo PITCH-BY-PITCH DATA COLLECTION - FULL RUN (2021-2025)
echo ================================================================================
echo.
echo This will collect pitch-level data for ALL MiLB players from 2021-2025
echo Expected time: 12-18 hours
echo Expected data: ~75-100M pitch records
echo.
echo Press Ctrl+C to cancel, or
pause

python run_all_pitch_collections.py

echo.
echo ================================================================================
echo COLLECTION COMPLETE!
echo ================================================================================
pause
