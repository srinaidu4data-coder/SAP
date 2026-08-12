@echo off
setlocal EnableExtensions
REM SAPILOT portable launcher (Profile A — attach to installed SAP GUI)
REM Zero install: uses embedded runtime if present, else system Python.

set "ROOT=%~dp0"
cd /d "%ROOT%"

REM Prefer embedded runtime
if exist "%ROOT%runtime\python\python.exe" (
  set "PYTHONHOME=%ROOT%runtime\python"
  set "PATH=%ROOT%runtime\python;%ROOT%runtime\python\Scripts;%PATH%"
  set "PY=%ROOT%runtime\python\python.exe"
) else (
  set "PY=python"
)

REM Side-load NW RFC SDK DLLs if present (no system PATH pollution)
if exist "%ROOT%runtime\nwrfcsdk\lib" (
  set "PATH=%ROOT%runtime\nwrfcsdk\lib;%PATH%"
  set "SAPNWRFC_HOME=%ROOT%runtime\nwrfcsdk"
)

set "SAPILOT_HOME=%ROOT%"
set "SAPILOT_DATA=%ROOT%data"
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"

"%PY%" -m sapilot %*
set "EC=%ERRORLEVEL%"
endlocal & exit /b %EC%
