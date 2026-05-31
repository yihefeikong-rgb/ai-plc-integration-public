@echo off
title TIA Portal IO 表创建
cd /d "%~dp0.."
echo 正在请求管理员权限...
powershell -Command "Start-Process python -ArgumentList 'tools/create_io_tag_table.py' -Verb RunAs -Wait"
pause
