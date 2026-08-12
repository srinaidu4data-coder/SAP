@echo off
REM SAPILOT local deploy — online co-pilot surfaces (localhost only)
cd /d "%~dp0"
set SAPILOT_LAB=1
set SAPILOT_ALLOW_UNSIGNED_POLICY=1
set SAPILOT_LIVE_GUI=1
set SAPILOT_FORCE_COM_BIND=1
set SAPILOT_SHOW_MOUSE=1
set SAPILOT_DATA=%~dp0data
set PYTHONPATH=%~dp0
set SAPILOT_VAULT_PASSPHRASE=%SAPILOT_VAULT_PASSPHRASE%

echo === SAPILOT DEPLOY (local) ===
echo   Copilot UI : http://127.0.0.1:8765
echo   Mega UI    : http://127.0.0.1:8777
echo   Auto bot   : http://127.0.0.1:8788
echo.

REM Prefer python from PATH
where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: python not on PATH
  exit /b 1
)

echo Starting Co-pilot webapp :8765 ...
start "SAPILOT-Copilot-8765" cmd /c "cd /d %~dp0 && set PYTHONPATH=%~dp0 && set SAPILOT_ALLOW_UNSIGNED_POLICY=1 && set SAPILOT_LAB=1 && set SAPILOT_DATA=%~dp0data && python -m sapilot.webapp.app"

timeout /t 2 /nobreak >nul

echo Starting Mega Co-pilot :8777 ...
start "SAPILOT-Mega-8777" cmd /c "cd /d %~dp0 && set PYTHONPATH=%~dp0 && set SAPILOT_ALLOW_UNSIGNED_POLICY=1 && set SAPILOT_LAB=1 && set SAPILOT_LIVE_GUI=1 && set SAPILOT_SHOW_MOUSE=1 && set SAPILOT_DATA=%~dp0data && python -m sapilot.mega.web"

timeout /t 2 /nobreak >nul

echo Starting Auto bot stealth UI :8788 ...
start "SAPILOT-Autobot-8788" cmd /c "cd /d %~dp0 && set PYTHONPATH=%~dp0 && set SAPILOT_ALLOW_UNSIGNED_POLICY=1 && set SAPILOT_LAB=1 && set SAPILOT_DATA=%~dp0data && python -m sapilot.autobot.stealth_ui"

echo.
echo Deployed locally. Open:
echo   http://127.0.0.1:8765
echo   http://127.0.0.1:8777
echo   http://127.0.0.1:8788
echo.
echo GitHub: https://github.com/srinaidu4data-coder/SAP
echo For live mouse: enable SAP GUI scripting + login Vista first.
exit /b 0
