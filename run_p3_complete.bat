@echo off
REM ========== AI 接入 PLC — P3 端到端流水线启动器 ==========
REM 以管理员权限运行完整流水线：编译 → 下载 → PLCSIM → Golden Backup
REM
REM 用法:
REM   run_p3_complete.bat          完整流水线（编译+下载）
REM   run_p3_complete.bat --no-compile  跳过编译，仅下载
REM   run_p3_complete.bat --help   显示帮助
REM =========================================================

setlocal enabledelayedexpansion

cd /d "%~dp0"

set PYTHON=D:\Python3\python.exe
set SCRIPTS=mcp-servers\tia-mcp
set ARGS=%*

if "%1"=="--help" (
    echo.
    echo AI 接入 PLC — P3 端到端流水线
    echo.
    echo 用法: run_p3_complete.bat [选项]
    echo.
    echo 选项:
    echo   --no-compile    跳过编译，仅下载到 PLCSIM
    echo   --help          显示此帮助
    echo.
    echo 步骤:
    echo   1. 从 golden backup 恢复 PLCSIM Advanced 实例
    echo   2. 启动 TIA Portal GUI（如未运行）
    echo   3. 编译项目
    echo   4. 下载到 PLCSIM
    echo   5. 更新 golden backup
    echo.
    pause
    exit /b 0
)

echo.
echo ========================================
echo  AI 接入 PLC — P3 端到端流水线
echo  以管理员权限运行
echo ========================================
echo.

REM Step 1: 恢复 PLCSIM
echo [Step 1/5] 恢复 PLCSIM Advanced 实例...
%PYTHON% %SCRIPTS%\plcsim_api.py list
if errorlevel 1 (
    echo  PLCSIM API 不可用，请确认已安装 PLCSIM Advanced V8.0
    pause
    exit /b 1
)
echo.

REM Step 2-4: 编译+下载
echo [Step 2-4/5] 启动 TIA Portal → 编译 → 下载到 PLCSIM...
echo   （若 TIA Portal 未运行将被自动启动）
echo.
if "%ARGS%"=="--no-compile" (
    %PYTHON% %SCRIPTS%\download_to_plcsim.py --ui
) else (
    %PYTHON% %SCRIPTS%\download_to_plcsim.py --compile-first
)
if errorlevel 1 (
    echo.
    echo ❌ 下载失败。手动步骤:
    echo   1. 在 TIA Portal GUI 中右键 PLC_1 → 下载到设备 → 软件(全部)
    echo   2. 运行: %PYTHON% %SCRIPTS%\plcsim_api.py archive factoryio ^
              "D:\PLC cheng xu\TIA PLC CHENG XU\demo\factory_io1_golden.zip" ^
              "D:\PLC cheng xu\TIA PLC CHENG XU\demo\plcsim_storage"
    pause
    exit /b 1
)
echo.

REM Step 5: 更新 golden backup
echo [Step 5/5] 更新 golden backup...
%PYTHON% -c "import sys; sys.path.insert(0,'%SCRIPTS%'); from plcsim_api import archive_instance; archive_instance('factoryio', 'D:\\PLC cheng xu\\TIA PLC CHENG XU\\demo\\factory_io1_golden.zip', 'D:\\PLC cheng xu\\TIA PLC CHENG XU\\demo\\plcsim_storage')"
echo.

echo ========================================
echo  ✅ P3 完整闭环完成！
echo   编译 ✅ → 下载 ✅ → Golden backup ✅
echo ========================================
pause
