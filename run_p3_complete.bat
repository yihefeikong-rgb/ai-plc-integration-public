@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

set PYTHON=D:\Python3\python.exe
set SCRIPTS=mcp-servers\tia-mcp
set GOLDEN="D:\PLC cheng xu\TIA PLC CHENG XU\demo\factory_io1_golden.zip"
set STORAGE="D:\PLC cheng xu\TIA PLC CHENG XU\demo\plcsim_storage"
set PLC_IP=10.0.0.1

echo.
echo ============================================
echo  AI to PLC - P3 End-to-End Pipeline
echo  Restore PLCSIM - Compile - Download - Backup
echo ============================================
echo.

REM ---- Step 0: Start PLCSIM from golden backup ----
echo [1/4] Restoring PLCSIM Advanced instance from golden backup...
%PYTHON% %SCRIPTS%\plcsim_api.py restore factoryio %GOLDEN% %STORAGE% %PLC_IP%
if errorlevel 1 (
    echo [FAIL] PLCSIM restore failed
    pause
    exit /b 1
)
echo [OK] PLCSIM running
echo.

REM ---- Step 1: Pre-check ----
echo [2/4] Verifying PLCSIM instance...
%PYTHON% %SCRIPTS%\plcsim_api.py list
if errorlevel 1 (
    echo [FAIL] PLCSIM not available
    pause
    exit /b 1
)
echo [OK]
echo.

REM ---- Step 2: Compile + Download ----
echo [3/4] Compile + Download to PLCSIM...
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
echo [OK] Download complete
echo.

REM ---- Step 3: Update Golden Backup ----
echo [4/4] Updating golden backup...
%PYTHON% scripts\archive_golden.py
if errorlevel 1 (
    echo [WARN] Golden backup update failed (non-fatal)
)
echo.

echo ============================================
echo  [DONE] P3 End-to-End Pipeline Complete
echo  PLCSIM [OK] - Compile [OK] - Download [OK]
echo ============================================
pause
