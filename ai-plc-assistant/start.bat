@echo off
chcp 65001 >nul
title AI PLC Assistant
echo ============================================
echo   AI PLC Assistant
echo ============================================
echo.

:: 清理端口 8005（后端）和 5173（前端）
echo Cleaning ports...
powershell -Command "Get-NetTCPConnection -LocalPort 8005 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }; Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
:: 等待端口释放
timeout /t 2 /nobreak >nul

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