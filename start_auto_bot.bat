@echo off
cd /d "%~dp0"
set SAPILOT_SHOW_MOUSE=1
set SAPILOT_ALLOW_UNSIGNED_POLICY=1
set SAPILOT_VAULT_PASSPHRASE=sapilot-local
set PYTHONPATH=%~dp0
echo SAP Auto AI Bot → http://127.0.0.1:8788
start "" "http://127.0.0.1:8788"
python -m sapilot.autobot
pause
