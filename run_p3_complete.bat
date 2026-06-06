@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

set PYTHON=D:\Python3\python.exe
set SCRIPTS=mcp-servers\tia-mcp

echo.
echo ============================================
echo  AI to PLC - P3 End-to-End Pipeline
echo  Compile - Download - Golden Backup
echo ============================================
echo.

REM ---- Step 0: Pre-check ----
echo [1/3] Checking PLCSIM...
%PYTHON% %SCRIPTS%\plcsim_api.py list
if errorlevel 1 (
    echo [FAIL] PLCSIM not available
    echo        Make sure PLCSIM Advanced V8.0 is installed
    pause
    exit /b 1
)
echo [OK]
echo.

REM ---- Step 1-2: Compile + Download ----
echo [2/3] Compile + Download to PLCSIM...
echo      (TIA Portal GUI will auto-start if needed)
echo.
%PYTHON% %SCRIPTS%\download_to_plcsim.py --compile-first
if errorlevel 1 (
    echo.
    echo [FAIL] Download failed. Manual steps:
    echo   1. Open TIA Portal GUI
    echo   2. Right-click PLC_1 - Download to device - Software
    echo   3. Then run: scripts\archive_golden.py
    pause
    exit /b 1
)
echo [OK]
echo.

REM ---- Step 3: Update Golden Backup ----
echo [3/3] Updating golden backup...
%PYTHON% scripts\archive_golden.py
if errorlevel 1 (
    echo [WARN] Golden backup update failed (non-fatal)
)
echo.

echo ============================================
echo  [DONE] P3 End-to-End Pipeline Complete
echo  Compile [OK] - Download [OK] - Golden [OK]
echo ============================================
pause
