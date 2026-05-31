@echo off
chcp 65001 >nul
echo ====================================
echo  材料小车 — 往复3次停止
echo ====================================
echo.

echo [1/3] 启动 lad_creator.py 创建 LAD 块...
echo 目标: D:\TIA FANG ZHEN\...
echo.

:: 改成你的仿真项目路径
set PROJECT_PATH=D:\TIA FANG ZHEN\PLC_DEMO.ap19

:: 读取 cart_3cycle.json 并传给 lad_creator.py
python lad_creator.py cart_3cycle.json

if %ERRORLEVEL% EQU 0 (
    echo ✅ LAD 块创建成功
) else (
    echo ❌ 创建失败，检查 TIA Portal 是否安装
)

pause
