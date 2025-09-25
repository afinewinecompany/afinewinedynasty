@echo off
echo ========================================
echo A Fine Wine Dynasty - API Testing Suite
echo ========================================

echo.
echo Installing Python requirements...
pip install -r requirements_api_validation.txt

echo.
echo ========================================
echo Running Comprehensive API Tests...
echo ========================================

echo.
echo 1. Running complete API validation suite...
python api_validation_suite.py

echo.
echo 2. Running detailed Fantrax integration test...
python fantrax_integration_test.py

echo.
echo ========================================
echo Testing Complete!
echo ========================================
echo Check the following files for results:
echo - api_validation_results.json
echo - fantrax_api_results_*.json
echo.

pause