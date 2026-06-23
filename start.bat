@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================
echo   AI PLC Integration — 一键启动所有服务
echo ============================================
echo.

cd /d "%~dp0.."

set PYTHON=D:\Python3\python.exe
set ORCHESTRATOR_PORT=8000
set BACKEND_PORT=8001

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

REM ── 1. orchestrator (编排层) ──
echo.
echo [1/5] 启动 orchestrator (端口 %ORCHESTRATOR_PORT%) ...
start "orchestrator" %PYTHON% -m uvicorn orchestrator.api:app --host 127.0.0.1 --port %ORCHESTRATOR_PORT%
echo [OK] orchestrator 已启动

REM 等待 orchestrator 就绪
timeout /t 2 >nul

REM ── 2. backend (后端) ──
echo [2/5] 启动 backend (端口 %BACKEND_PORT%) ...
start "backend" %PYTHON% -m uvicorn ai-plc-assistant.backend.main:app --host 127.0.0.1 --port %BACKEND_PORT%
echo [OK] backend 已启动

REM ── 3. plc-mcp-bridge ──
echo [3/5] 启动 plc-mcp-bridge ...
start "plc-mcp-bridge" %PYTHON% mcp-servers\plc-mcp-bridge\server.py
echo [OK] plc-mcp-bridge 已启动

REM ── 4. tia-mcp ──
echo [4/5] 启动 tia-mcp ...
start "tia-mcp" %PYTHON% mcp-servers\tia-mcp\server.py
echo [OK] tia-mcp 已启动

REM ── 5. robot-mcp ──
echo [5/5] 启动 robot-mcp ...
start "robot-mcp" %PYTHON% mcp-servers\robot-mcp\server.py
echo [OK] robot-mcp 已启动

echo.
echo ============================================
echo   启动完成
echo ============================================
echo.
echo   运行中的服务:
echo     orchestrator    http://127.0.0.1:%ORCHESTRATOR_PORT%
echo     backend         http://127.0.0.1:%BACKEND_PORT%
echo     plc-mcp-bridge  (stdio MCP)
echo     tia-mcp         (stdio MCP)
echo     robot-mcp       (stdio MCP)
echo.
echo   下一步:
echo     1. 打开 TIA Portal (管理员权限)
echo     2. 运行冒烟测试: %PYTHON% scripts\e2e_smoke.py
echo     3. 或运行演示:   %PYTHON% scripts\demo.py
echo     4. 打开前端:     http://localhost:5173
echo.
echo   停止服务: 关闭各个命令行窗口
echo.
pause
