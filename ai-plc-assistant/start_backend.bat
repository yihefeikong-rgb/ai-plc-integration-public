@echo off
chcp 65001 >nul
title AI-PLC Backend
cd /d "%~dp0backend"
echo Cleaning port 8005...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8005" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
echo.
echo backend starting on port 8005...
"D:\Python3\python.exe" main.py
pause