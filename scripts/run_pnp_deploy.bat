@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Pick & Place One-Click Deploy
REM  Create Tags -> Import SCL -> Compile -> Download -> FIO -> Robot MCP
REM
REM  Usage (run AS ADMINISTRATOR):
REM    scripts\run_pnp_deploy.bat
REM    scripts\run_pnp_deploy.bat --skip-tia
REM ============================================================

cd /d "%~dp0.."

REM ---- Check admin privileges ----
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] This script requires Administrator privileges.
    echo        Please right-click this bat file and "Run as administrator",
    echo        or run from an elevated Command Prompt / PowerShell.
    pause
    exit /b 1
)
echo [OK] Running as Administrator

set PYTHON=D:\Python3\python.exe
set CREATE_TAGS=mcp-servers\tia-mcp\create_plc_tags.py
set DEPLOY_PNP=mcp-servers\robot-mcp\deploy_pnp.py
set TAGS_JSON=mcp-servers\robot-mcp\pnp_tags.json

REM ---- Check Python ----
if not exist "%PYTHON%" (
    echo [FAIL] Python not found: %PYTHON%
    echo        Please check D:\Python3\python.exe exists
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Pick ^& Place One-Click Deploy
echo  Python: %PYTHON%
echo  Root:   %CD%
echo ============================================
echo.

REM ---- Phase 1: Create PLC tag table ----
set SKIP_TIA=0
if "%1"=="--skip-tia" set SKIP_TIA=1

if %SKIP_TIA% equ 0 (
    echo [1/2] Creating PLC I/O tag table (PickAndPlace_IO)...
    echo.
    %PYTHON% %CREATE_TAGS% --tags %TAGS_JSON%
    if errorlevel 1 (
        echo.
        echo [FAIL] Tag creation failed.
        echo        Please check:
        echo          1. TIA Portal V21 is open and project is not locked
        echo          2. Project path in config.yaml or .env is correct
        echo          3. If old tag table exists, try clearing it first
        pause
        exit /b 1
    )
    echo.
    echo [OK] Tag creation complete
    echo.
) else (
    echo [SKIP] Skipping tag creation
    echo.
)

REM ---- Phase 2: Full deploy (SCL import + compile + download + FIO + Robot MCP) ----
if %SKIP_TIA% equ 0 (
    echo [2/2] Full deploy (SCL import -> compile -> download -> FIO -> Robot MCP)...
) else (
    echo [2/2] Starting Factory I/O + Robot MCP...
)
echo.

%PYTHON% %DEPLOY_PNP% %1
if errorlevel 1 (
    echo.
    echo [FAIL] Deploy failed.
    echo        Please check TIA Portal and PLCSIM status.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  [DONE] Deploy Complete!
echo  AI can control the robot via Robot MCP:
echo    status()     -- check robot status
echo    home()       -- reset to safe position
echo    pick()       -- pick from entry
echo    place()      -- place to exit
echo    run_cycle(5) -- auto repeat 5 cycles
echo ============================================
echo.
pause
