@echo off
chcp 65001 >nul
title AI PLC Assistant
echo ============================================
echo   AI PLC Assistant
echo ============================================
echo.

:: ── 拒绝占用中的端口，避免误杀无关进程 ──
echo [1/4] 检查端口 8005 和 5173 ...
powershell -NoProfile -Command "$busy = @(Get-NetTCPConnection -LocalPort 8005,5173 -State Listen -ErrorAction SilentlyContinue); if ($busy.Count -gt 0) { $busy | ForEach-Object { Write-Host ('[FAIL] Port ' + $_.LocalPort + ' is already in use by PID ' + $_.OwningProcess) }; exit 1 }"
if errorlevel 1 (
    echo [FAIL] 启动端口已被占用；请确认并手动关闭对应服务后重试。
    pause
    exit /b 1
)

:: ── MCP owner lock 由后端校验，启动脚本不得擅自删除 ──
echo [2/4] MCP 所有权锁由后端安全校验 ...

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
