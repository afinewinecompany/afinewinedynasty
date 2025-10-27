@echo off
:: BMAD Sync - Update BMAD to Latest Version
:: Run this script to sync your BMAD installation

echo =========================================
echo           BMAD SYNC UTILITY
echo =========================================
echo.

cd /d "%~dp0"

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.x to use this script
    pause
    exit /b 1
)

:: Run the sync with the provided arguments or default to status check
if "%1"=="" (
    echo Checking BMAD status...
    python bmad_sync.py --status
    echo.
    echo To update BMAD, run: BMAD_SYNC.bat update
) else if "%1"=="update" (
    python bmad_sync.py --update
) else if "%1"=="force" (
    python bmad_sync.py --force
) else if "%1"=="status" (
    python bmad_sync.py --status
) else (
    echo Invalid argument: %1
    echo.
    echo Usage:
    echo   BMAD_SYNC.bat         - Check status
    echo   BMAD_SYNC.bat update  - Update to latest version
    echo   BMAD_SYNC.bat force   - Force update (even if up to date)
    echo   BMAD_SYNC.bat status  - Check current installation status
)

echo.
pause