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
echo  AI to PLC - End-to-End Pipeline
echo  PLCSIM + Factory IO + Compile + Download
echo ============================================
echo.

REM ---- Step 1: Start PLCSIM from golden backup ----
echo [1/5] Starting PLCSIM...
%PYTHON% %SCRIPTS%\plcsim_api.py restore factoryio %GOLDEN% %STORAGE% %PLC_IP%
if errorlevel 1 (
    echo [FAIL] PLCSIM restore failed
    pause
    exit /b 1
)
echo [OK] PLCSIM running
echo.

REM ---- Step 2: Launch Factory I/O ----
echo [2/5] Starting Factory I/O...
%PYTHON% scripts\launch_factory_io.py
if errorlevel 1 (
    echo [WARN] Factory I/O launch failed (non-fatal)
    echo        You can start it manually later
) else (
    echo [OK] Factory I/O starting
)
echo.

REM ---- Step 3: Compile + Download ----
echo [3/5] Compile + Download to PLCSIM...
%PYTHON% %SCRIPTS%\download_to_plcsim.py --compile-first
if errorlevel 1 (
    echo.
    echo [FAIL] Download failed. Manual steps:
    echo   1. Open TIA Portal GUI as Administrator
    echo   2. Right-click PLC_1 - Download to device - Software
    echo   3. Then run: scripts\archive_golden.py
    pause
    exit /b 1
)
echo [OK] Download complete
echo.

REM ---- Step 4: Update Golden Backup ----
echo [4/5] Updating golden backup...
%PYTHON% scripts\archive_golden.py
if errorlevel 1 (
    echo [WARN] Golden backup update failed (non-fatal)
)
echo.

echo ============================================
echo  [DONE] Pipeline Complete
echo  PLCSIM [OK] - Factory IO [OK] - Download [OK]
echo ============================================
echo  Next steps:
echo  1. Check PLCSIM: %PYTHON% %SCRIPTS%\plcsim_api.py list
echo  2. Open Factory I/O window to see the simulation
echo  3. To stop: %PYTHON% %SCRIPTS%\plcsim_api.py stop factoryio
echo.
pause
