@echo off
cd /d "%~dp0"
python scripts\pack_portable.py
if errorlevel 1 exit /b 1
echo.
echo Copy dist\SAPILOT-portable.zip (or the folder) to the other PC.
echo On that PC: unzip and run CHECK.bat
exit /b 0
