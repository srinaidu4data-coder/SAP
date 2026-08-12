@echo off
setlocal
cd /d "%~dp0"
set SAPILOT_HOME=%~dp0
set SAPILOT_DATA=%~dp0data
set SAPILOT_ALLOW_UNSIGNED_POLICY=1
set SAPILOT_SHOW_MOUSE=1
if not defined SAPILOT_VAULT_PASSPHRASE set SAPILOT_VAULT_PASSPHRASE=sapilot-local
set PYTHONPATH=%~dp0

echo.
echo  ============================================
echo   MEGA SAP COPILOT
echo   http://127.0.0.1:8777
echo  ============================================
echo.

start "" "http://127.0.0.1:8777"
python -m sapilot.mega.web
pause
