@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================
echo   AI PLC Integration — 一键启动所有服务
echo ============================================
echo.

cd /d "%~dp0"

set PYTHON=D:\Python3\python.exe
set BACKEND_PORT=8005

REM ── 检查 Python ──
if not exist "%PYTHON%" (
    echo [FAIL] Python 未找到: %PYTHON%
    echo        请修改 start.bat 中的 PYTHON 路径
    pause
    exit /b 1
)
echo [OK] Python: %PYTHON%

REM ── 前置检查 ──
echo.
echo 运行前置检查 ...
%PYTHON% scripts\preflight.py
if errorlevel 1 (
    echo.
    echo [WARN] 部分前置条件不满足，详见上方报告
    echo        是否继续启动? 按任意键继续 / Ctrl+C 取消
    pause >nul
)

REM ── 1. backend（内部 orchestrator 是唯一 MCP 生命周期所有者） ──
echo.
echo [1/1] 启动 backend (端口 %BACKEND_PORT%) ...
start "backend" %PYTHON% -m uvicorn ai-plc-assistant.backend.main:app --host 127.0.0.1 --port %BACKEND_PORT%
echo [OK] backend 已启动
echo [INFO] MCP 服务器由 backend 内部 orchestrator 独占管理；本脚本不会重复启动 stdio MCP 进程

echo.
echo ============================================
echo   启动完成
echo ============================================
echo.
echo   运行中的服务:
echo     backend         http://127.0.0.1:%BACKEND_PORT%
echo     MCP servers     由 backend 内部 orchestrator 按 stdio 生命周期管理
echo.
echo   下一步:
echo     1. 先检查 /health，确认服务已启动
echo     2. 控制、下载和仿真操作必须另行经过隔离目标与人工确认
echo     3. 本脚本不启动前端、TIA Portal、PLCSIM 或 Factory I/O
echo.
echo   停止服务: 关闭各个命令行窗口
echo.
pause
