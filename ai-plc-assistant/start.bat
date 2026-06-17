@echo off
chcp 65001 >nul
title AI PLC Assistant
echo ============================================
echo   AI PLC Assistant
echo ============================================
echo.
echo Cleaning port 8005...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8005" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
cd /d "%~dp0backend"
start "backend" cmd /k "D:\Python3\python.exe" main.py
ping 127.0.0.1 -n 6 >nul
cd /d "%~dp0frontend"
start "frontend" cmd /k npm run dev
echo.
echo   backend: http://127.0.0.1:8005
echo   frontend: Electron
echo ============================================
pause