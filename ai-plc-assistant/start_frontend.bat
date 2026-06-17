@echo off
chcp 65001 >nul
title AI-PLC Frontend
cd /d "%~dp0frontend"
echo frontend starting...
npm run dev
pause