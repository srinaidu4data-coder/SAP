@echo off
cd /d %~dp0
set SAPILOT_LAB=1
set SAPILOT_ALLOW_UNSIGNED_POLICY=1
set SAPILOT_LIVE_GUI=1
set SAPILOT_FORCE_COM_BIND=1
set SAPILOT_SHOW_MOUSE=1
set SAPILOT_DATA=%~dp0data
set PYTHONPATH=%~dp0
echo === PRODUCT MODE: ONLINE GUI + MOUSE (not twin skip) ===
echo Require: SAP Logon scripting ON, RZ11 sapgui/user_scripting=TRUE, logged into Vista
echo === ONLINE HEALTH ===
python -m sapilot online-health
echo === ONLINE 22 (GUI required) ===
python -m sapilot online-20 --no-fallback
echo === SUPER BOT ONLINE ===
python scripts\run_super_bot.py
if errorlevel 1 (
  echo FAILED: online GUI did not complete. Fix scripting/session and re-run.
)
pause
