@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0
set SAPILOT_DATA=%~dp0data
set SAPILOT_LAB=1
set SAPILOT_ALLOW_UNSIGNED_POLICY=1
set SAPILOT_SHOW_MOUSE=1
echo.
echo  SAPILOT product
echo  http://127.0.0.1:8800
echo  Leave SAP Easy Access visible. Keep this window open.
echo.
start "" "http://127.0.0.1:8800"
python -m sapilot product
pause
