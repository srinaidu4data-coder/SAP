@echo off
REM Optional: package Co-pilot UI as a Windows .exe (requires PyInstaller)
cd /d "%~dp0"
python -m pip install pyinstaller flask -q
python -m PyInstaller --noconfirm --clean ^
  --name SAPILOT-Copilot ^
  --add-data "sapilot/webapp/templates;sapilot/webapp/templates" ^
  --add-data "sapilot/webapp/static;sapilot/webapp/static" ^
  --add-data "sapilot/policy;sapilot/policy" ^
  --add-data "sapilot/copilot/scenarios;sapilot/copilot/scenarios" ^
  --add-data "sapilot/know;sapilot/know" ^
  --add-data "sapilot/brain/prompts;sapilot/brain/prompts" ^
  --hidden-import win32timezone ^
  --hidden-import sapilot.webapp.app ^
  -m sapilot.webapp.app

echo.
echo If build succeeded, run: dist\SAPILOT-Copilot\SAPILOT-Copilot.exe
echo Then open http://127.0.0.1:8765
pause
