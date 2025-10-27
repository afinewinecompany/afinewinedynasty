@echo off
echo ================================================================================
echo STARTING 2024 MiLB DATA COLLECTION
echo ================================================================================
echo.
echo This will collect 2024 MiLB data for:
echo   - Batters: Plate appearances and pitch-by-pitch data
echo   - Pitchers: Game logs and pitch-by-pitch data
echo.
echo Collections will run in parallel in separate windows.
echo.
pause

echo.
echo Starting 2024 Batter Collection...
start "2024 Batter Collection" cmd /k "cd /d %~dp0 && python collect_2024_batter_data_robust.py"

echo.
echo Waiting 5 seconds before starting pitcher collection...
timeout /t 5 /nobreak

echo.
echo Starting 2024 Pitcher Collection...
start "2024 Pitcher Collection" cmd /k "cd /d %~dp0 && python collect_2024_pitcher_data_robust.py"

echo.
echo ================================================================================
echo BOTH COLLECTIONS STARTED
echo ================================================================================
echo.
echo Check the separate windows to monitor progress.
echo Log files will be created in the logs/ directory:
echo   - logs/2024_batter_collection.log
echo   - logs/2024_pitcher_collection.log
echo.
echo Press any key to exit this window...
pause > nul
