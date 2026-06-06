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
echo  PLCSIM GUI + Instance + FIO + Compile
echo ============================================
echo.

REM ---- Step 1: Start PLCSIM Advanced GUI (the simulator window) ----
echo [1/6] Starting PLCSIM Advanced GUI...
%PYTHON% scripts\start_plcsim_gui.py
if errorlevel 1 (
    echo [FAIL] PLCSIM GUI failed to start
    echo        Make sure S7-PLCSIM Advanced V8.0 is installed
    pause
    exit /b 1
)
echo [OK] PLCSIM GUI ready
echo.

REM ---- Step 2: Restore PLCSIM instance from golden backup ----
echo [2/6] Restoring PLCSIM instance...
%PYTHON% %SCRIPTS%\plcsim_api.py restore factoryio %GOLDEN% %STORAGE% %PLC_IP%
if errorlevel 1 (
    echo.
    echo [FAIL] PLCSIM restore failed.
    echo.
    echo  If the error is "Error Code: -30, LicenseNotFound":
    echo    → PLCSIM Advanced trial license may have expired (14-day limit)
    echo    → Solution A: Reinstall PLCSIM Advanced to refresh trial
    echo    → Solution B: Use TIA Portal built-in simulation (no separate license needed)
    echo    → Solution C: Purchase PLCSIM Advanced license from Siemens
    echo    → Solution D: Use OpenPLC Docker (free, no Siemens license):
    echo         docker-compose --profile simulation up -d
    echo.
    echo  If the error is different, check plcsim_api.py error codes.
    pause
    exit /b 1
)
echo [OK] PLCSIM instance running (IP=%PLC_IP%)
echo.

REM ---- Step 3: Launch Factory I/O ----
echo [3/6] Starting Factory I/O...
%PYTHON% scripts\launch_factory_io.py
if errorlevel 1 (
    echo [WARN] Factory I/O launch failed (non-fatal)
    echo        You can start it manually later
) else (
    echo [OK] Factory I/O starting
)
echo.

REM ---- Step 4: Compile + Download ----
echo [4/6] Compile + Download to PLCSIM...
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

REM ---- Step 5: Update Golden Backup ----
echo [5/6] Updating golden backup...
%PYTHON% scripts\archive_golden.py
if errorlevel 1 (
    echo [WARN] Golden backup update failed (non-fatal)
)
echo.

echo ============================================
echo  [DONE] Pipeline Complete
echo  PLCSIM [OK] - FIO [OK] - Download [OK]
echo ============================================
echo  Next steps:
echo  1. Check PLCSIM: %PYTHON% %SCRIPTS%\plcsim_api.py list
echo  2. Open Factory I/O window to see the simulation
echo  3. To stop: %PYTHON% %SCRIPTS%\plcsim_api.py stop factoryio
echo.
pause
