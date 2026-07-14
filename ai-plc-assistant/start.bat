@echo off
chcp 65001 >nul
title AI PLC Assistant
echo ============================================
echo   AI PLC Assistant
echo ============================================
echo.

:: 端口被占用时拒绝启动，绝不终止未知进程。
echo Checking ports...
powershell -NoProfile -Command "$ports = @(8005, 5173); $busy = @($ports | Where-Object { Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue }); if ($busy.Count -gt 0) { Write-Host ('[FAIL] Port(s) already in use: ' + ($busy -join ', ')); exit 1 }"
if errorlevel 1 (
    echo [FAIL] 端口 8005 或 5173 已被占用；请确认并手动关闭对应服务后重试。
    pause
    exit /b 1
)

cd /d "%~dp0backend"
start "backend" cmd /k "D:\Python3\python.exe" main.py
ping 127.0.0.1 -n 6 >nul
cd /d "%~dp0frontend"
start "frontend" cmd /k npm run dev
echo.
echo   backend: http://127.0.0.1:8005
echo   frontend: http://localhost:5173
echo ============================================
pause
