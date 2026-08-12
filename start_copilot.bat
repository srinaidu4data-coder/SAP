@echo off
setlocal
cd /d "%~dp0"
set SAPILOT_HOME=%~dp0
set SAPILOT_DATA=%~dp0data
set SAPILOT_ALLOW_UNSIGNED_POLICY=1
if not defined SAPILOT_VAULT_PASSPHRASE set SAPILOT_VAULT_PASSPHRASE=sapilot-local
set PYTHONPATH=%~dp0

echo.
echo  SAPILOT Co-pilot
echo  Opening http://127.0.0.1:8765
echo  Keep this window open.
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Python not found on PATH.
  pause
  exit /b 1
)

start "" "http://127.0.0.1:8765"
python -m sapilot.webapp.app
pause
