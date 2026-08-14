"""
Build a Profile-A portable folder: embedded CPython + wheels + sapilot.
Host still supplies SAP GUI. No admin install required on the other PC.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CACHE = ROOT / ".cache"
PACK_NAME = "SAPILOT-portable"
PACK = DIST / PACK_NAME
PY_VER = "3.12.10"
EMBED_URL = f"https://www.python.org/ftp/python/{PY_VER}/python-{PY_VER}-embed-amd64.zip"
GETPIP_URL = "https://bootstrap.pypa.io/get-pip.py"

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".grok",
    ".cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "dist",
    "runtime",
    "node_modules",
    "_docx_build",
    "sapilot.egg-info",
    ".docx-tmp",
}


def _copy_tree(src: Path, dst: Path, *, skip_names: set[str] | None = None) -> None:
    skip = skip_names or SKIP_DIR_NAMES
    if dst.exists():
        shutil.rmtree(dst)
    def ignore(directory: str, names: list[str]) -> set[str]:
        dropped = set()
        for n in names:
            if n in skip or n.endswith(".pyc"):
                dropped.add(n)
        return dropped
    shutil.copytree(src, dst, ignore=ignore)


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"  cache hit {dest.name}")
        return
    print(f"  download {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace("\n", "\r\n"), encoding="utf-8")


def _layout_python(runtime: Path) -> None:
    zip_path = CACHE / f"python-{PY_VER}-embed-amd64.zip"
    _download(EMBED_URL, zip_path)
    if runtime.exists():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(runtime)

    pth = next(runtime.glob("python*._pth"))
    pth.write_text(
        "python312.zip\n"
        ".\n"
        "Lib\\site-packages\n"
        "..\\..\n"
        "import site\n",
        encoding="utf-8",
    )

    getpip = CACHE / "get-pip.py"
    _download(GETPIP_URL, getpip)
    py = runtime / "python.exe"
    subprocess.check_call([str(py), str(getpip), "--no-warn-script-location"])


def _pip(runtime: Path, *args: str) -> None:
    py = runtime / "python.exe"
    subprocess.check_call(
        [str(py), "-m", "pip", "install", "--no-warn-script-location", *args]
    )


def _fix_pywin32(runtime: Path) -> None:
    """Copy pywin32 DLLs next to python.exe so COM works without admin postinstall."""
    site = runtime / "Lib" / "site-packages"
    sys32 = site / "pywin32_system32"
    if not sys32.is_dir():
        print("  pywin32_system32 missing — GUI channel will be optional")
        return
    for dll in sys32.glob("*.dll"):
        shutil.copy2(dll, runtime / dll.name)
    # win32 package looks for pywintypes in site-packages/win32
    win32 = site / "win32"
    if win32.is_dir():
        for dll in sys32.glob("*.dll"):
            shutil.copy2(dll, win32 / dll.name)


def _copy_payload() -> None:
    _copy_tree(ROOT / "sapilot", PACK / "sapilot")
    _copy_tree(ROOT / "tests", PACK / "tests")
    docs_src = ROOT / "docs"
    docs_dst = PACK / "docs"
    docs_dst.mkdir(parents=True, exist_ok=True)
    for name in (
        "CONSULTANT_BRIEFING.md",
        "CONSULTANT_BRIEFING.docx",
        "DISPLAY_WING.md",
        "HUMAN_OPERATOR.md",
        "ANALYSIS_WING.md",
        "PORTABLE.md",
    ):
        src = docs_src / name
        if src.exists():
            shutil.copy2(src, docs_dst / name)
    shutil.copy2(ROOT / "requirements.txt", PACK / "requirements.txt")
    shutil.copy2(ROOT / "pyproject.toml", PACK / "pyproject.toml")
    shutil.copy2(ROOT / "run.bat", PACK / "run.bat")
    scope = ROOT / ".grok" / "OPERATOR_SCOPE.md"
    if scope.exists():
        shutil.copy2(scope, PACK / "docs" / "OPERATOR_SCOPE.md")
    (PACK / "data" / "runs").mkdir(parents=True, exist_ok=True)
    (PACK / "data" / "vault").mkdir(parents=True, exist_ok=True)
    (PACK / "data" / "runs" / ".gitkeep").write_text("", encoding="utf-8")


LAUNCHER = r'''@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"
set "PY=%ROOT%runtime\python\python.exe"
if not exist "%PY%" (
  echo ERROR: embedded Python missing at runtime\python\python.exe
  echo This folder is incomplete. Copy the whole SAPILOT-portable directory.
  exit /b 1
)
set "PYTHONHOME=%ROOT%runtime\python"
set "PATH=%ROOT%runtime\python;%ROOT%runtime\python\Scripts;%PATH%"
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"
set "SAPILOT_HOME=%ROOT%"
set "SAPILOT_DATA=%ROOT%data"
set "SAPILOT_LAB=1"
set "SAPILOT_ALLOW_UNSIGNED_POLICY=1"
"%PY%" -m sapilot %*
set "EC=%ERRORLEVEL%"
endlocal & exit /b %EC%
'''

CHECK = r'''@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"
set "PY=%ROOT%runtime\python\python.exe"
set "PYTHONHOME=%ROOT%runtime\python"
set "PATH=%ROOT%runtime\python;%ROOT%runtime\python\Scripts;%PATH%"
set "PYTHONPATH=%ROOT%"
set "SAPILOT_HOME=%ROOT%"
set "SAPILOT_DATA=%ROOT%data"
set "SAPILOT_LAB=1"
set "SAPILOT_ALLOW_UNSIGNED_POLICY=1"
set "SAPILOT_OFFLINE=1"
echo === SAPILOT portable self-test (no SAP required) ===
echo This pack is a GENERAL SAP GUI operator. No single process is the product.
echo.
echo [1/5] Python
"%PY%" -c "import sys; print(sys.version)"
if errorlevel 1 exit /b 1
echo [2/5] Preflight
"%PY%" -m sapilot preflight
if errorlevel 1 exit /b 1
echo [3/5] Display wing is process-agnostic
"%PY%" -m sapilot display list
"%PY%" -m sapilot display plan
if errorlevel 1 exit /b 1
echo [4/5] Create/change/post refused across modules
"%PY%" "%ROOT%tests\_portable_policy_smoke.py"
if errorlevel 1 exit /b 1
echo [5/5] Unit tests that travel with the pack
"%PY%" -m pytest tests/test_display_wing.py tests/test_preflight.py tests/test_policy.py tests/test_governor.py tests/test_operator_eyes_hands.py -q
if errorlevel 1 exit /b 1
echo.
echo PASS — the operator pack works on this PC without SAP.
echo Any module, any display t-code. Examples in the catalog are examples.
echo Live SAP GUI still needs SAP Logon on that PC (host supplies GUI).
exit /b 0
'''

START = r'''@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title SAPILOT portable
echo.
echo   SAPILOT — general SAP GUI operator
echo   Any module. Any t-code. Display wing never creates.
echo   -----------------------------------------------
echo   1  Self-test this PC (no SAP needed)
echo   2  What this app is (command help)
echo   3  Example display spines (examples only)
echo   4  Co-pilot web UI  http://127.0.0.1:8765
echo   5  Operator see (needs live SAP GUI)
echo   9  Exit
echo.
set /p C=Choose: 
if "%C%"=="1" call "%~dp0CHECK.bat" & goto end
if "%C%"=="2" call "%~dp0SAPILOT.bat" --help & echo. & call "%~dp0SAPILOT.bat" operator --help & echo. & call "%~dp0SAPILOT.bat" display --help & goto end
if "%C%"=="3" call "%~dp0SAPILOT.bat" display list & call "%~dp0SAPILOT.bat" display plan & goto end
if "%C%"=="4" start "" "%~dp0START_COPILOT.bat" & goto end
if "%C%"=="5" call "%~dp0SAPILOT.bat" operator see & goto end
if "%C%"=="9" exit /b 0
echo Unknown choice
:end
echo.
pause
'''

START_COPILOT = r'''@echo off
cd /d "%~dp0"
set "PY=%~dp0runtime\python\python.exe"
set "PYTHONHOME=%~dp0runtime\python"
set "PATH=%~dp0runtime\python;%~dp0runtime\python\Scripts;%PATH%"
set "PYTHONPATH=%~dp0"
set "SAPILOT_DATA=%~dp0data"
set "SAPILOT_LAB=1"
set "SAPILOT_ALLOW_UNSIGNED_POLICY=1"
echo Co-pilot UI — http://127.0.0.1:8765
start "" http://127.0.0.1:8765
"%PY%" -m sapilot.webapp.app
'''

README = """SAPILOT portable — general SAP GUI operator
==========================================

This is not a purchase-order app. It is not a payment-run app.
It is a person at the SAP GUI for ANY module, ANY t-code, ANY process.

Named cycles in the catalog (buy, sell, cost, collect, …) are EXAMPLES.
The last process we tested is not the product.

What travels with the stick
---------------------------
- Embedded Python 3.12 (no install, no admin)
- Operator: see / goto / fill / click / prove
- Display wing: display t-codes only (create/change/post refused)
- Analysis docs

What the OTHER PC must already have
-----------------------------------
- Windows 10/11 64-bit
- For LIVE SAP: SAP GUI for Windows + Logon Pad (we do not ship SAP)
- Optional: Tesseract OCR for vision eyes
  Default: C:\\Program Files\\Tesseract-OCR\\tesseract.exe

How to see if it works
----------------------
1. Copy the WHOLE folder (or unzip). Do not scatter files.
2. Double-click CHECK.bat  (no SAP needed)
3. If PASS, double-click START.bat
4. Logged into any SAP screen on that PC:
     SAPILOT.bat operator see
     SAPILOT.bat operator goto <ANY_DISPLAY_TCODE>
     SAPILOT.bat display goto <ANY_DISPLAY_TCODE>
   Create / change / post t-codes are refused in the display wing.

Command line
------------
  SAPILOT.bat preflight
  SAPILOT.bat operator see
  SAPILOT.bat operator goto VA03
  SAPILOT.bat display list
  SAPILOT.bat display plan
  SAPILOT.bat display walk <example-or-your-name>

Do not copy data\\vault, .env, or passwords.
"""


def _launchers() -> None:
    _write(PACK / "SAPILOT.bat", LAUNCHER)
    _write(PACK / "CHECK.bat", CHECK)
    _write(PACK / "START.bat", START)
    _write(PACK / "START_COPILOT.bat", START_COPILOT)
    (PACK / "README-PORTABLE.txt").write_text(README, encoding="utf-8")


def _selftest() -> None:
    print("=== self-test inside the pack ===")
    subprocess.check_call(["cmd", "/c", str(PACK / "CHECK.bat")], cwd=PACK)


def _zip() -> Path:
    zip_path = DIST / f"{PACK_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    print(f"zip {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in PACK.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(DIST))
    mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  {zip_path}  {mb:.1f} MB")
    return zip_path


def main() -> int:
    refresh = "--refresh" in sys.argv
    DIST.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    runtime = PACK / "runtime" / "python"
    if refresh and (runtime / "python.exe").exists():
        print("refresh: keep embedded Python, replace app + launchers")
        _copy_payload()
        _launchers()
        _selftest()
        z = _zip()
        print("READY", PACK, z)
        return 0
    if PACK.exists():
        print("clearing previous pack")
        shutil.rmtree(PACK)
    PACK.mkdir(parents=True)

    print("1. payload")
    _copy_payload()
    print("2. embed Python")
    _layout_python(runtime)
    print("3. pip packages")
    _pip(
        runtime,
        "pydantic>=2.6",
        "pyyaml>=6.0",
        "tenacity>=8.2",
        "jinja2>=3.1",
        "requests>=2.31",
        "openai>=1.40",
        "cryptography>=42.0",
        "rich>=13.7",
        "click>=8.1",
        "flask>=3.0",
        "pillow>=10.0",
        "pytesseract>=0.3.10",
        "pytest>=8.0",
        "pywin32>=306",
    )
    print("4. pywin32 portable DLLs")
    _fix_pywin32(runtime)
    print("5. launchers")
    _launchers()
    print("6. self-test")
    _selftest()
    print("7. zip")
    z = _zip()
    print()
    print("READY")
    print(f"  folder: {PACK}")
    print(f"  zip:    {z}")
    print("  copy the folder or the zip to another Windows PC and run CHECK.bat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
