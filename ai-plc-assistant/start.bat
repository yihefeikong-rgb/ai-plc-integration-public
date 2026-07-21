@echo off
chcp 65001 >nul
title AI PLC Assistant
echo ============================================
echo   AI PLC Assistant
echo ============================================
echo.

:: ── 杀掉旧进程 ──
echo [1/4] 清理旧进程 ...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8005,5173 -ErrorAction SilentlyContinue | ForEach-Object { $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; if ($p) { Write-Host ('  杀掉端口 ' + $_.LocalPort + ' 上的进程 (PID ' + $_.OwningProcess + ')'); Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"

:: ── 清理 MCP 锁 ──
echo [2/4] 清理 MCP 锁文件 ...
if exist "%TEMP%\ai-plc-mcp-owner.lock" (
    del /f /q "%TEMP%\ai-plc-mcp-owner.lock" >nul 2>&1
    echo   已删除陈旧 MCP 锁文件
)

:: ── 启动后端 ──
echo [3/4] 启动后端 (端口 8005) ...
cd /d "%~dp0backend"
start "backend" cmd /k "D:\Python3\python.exe" main.py
ping 127.0.0.1 -n 6 >nul

:: ── 启动前端 ──
echo [4/4] 启动前端 (端口 5173) ...
cd /d "%~dp0frontend"
start "frontend" cmd /k npm run dev
echo.
echo   backend: http://127.0.0.1:8005
echo   frontend: http://localhost:5173
echo ============================================
pause
