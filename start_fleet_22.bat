@echo off
cd /d %~dp0
set SAPILOT_LAB=1
set SAPILOT_ALLOW_UNSIGNED_POLICY=1
set SAPILOT_DATA=%~dp0data
set PYTHONPATH=%~dp0
echo === FLEET 22: 10 PTP + 10 OTC + 2 ABAP ===
python -m sapilot super-bot
python -m sapilot mission-critical --no-gui
python -m sapilot karpathy-tick
pause
