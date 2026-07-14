@echo off
chcp 65001 >nul
title AI-PLC Backend
cd /d "%~dp0backend"
echo Checking port 8005...
powershell -NoProfile -Command "$busy = @(Get-NetTCPConnection -LocalPort 8005 -State Listen -ErrorAction SilentlyContinue); if ($busy.Count -gt 0) { Write-Host '[FAIL] Port 8005 is already in use'; exit 1 }"
if errorlevel 1 (
    echo [FAIL] 端口 8005 已被占用；请确认并手动关闭对应服务后重试。
    pause
    exit /b 1
)
echo.
echo backend starting on port 8005...
"D:\Python3\python.exe" main.py
pause
