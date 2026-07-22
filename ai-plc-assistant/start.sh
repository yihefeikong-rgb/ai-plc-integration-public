#!/bin/bash
# AI PLC Assistant 启动脚本 (Git Bash / WSL)

PORT=8005
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "===================================="
echo "  AI PLC Assistant - 启动中..."
echo "===================================="
echo ""

# 清理旧进程
kill $(lsof -ti:$PORT) 2>/dev/null

# 启动后端
echo "[1/2] 启动后端 (:$PORT)"
cd "$SCRIPT_DIR/backend"
python main.py &
BACKEND_PID=$!
sleep 4

# 启动前端
echo "[2/2] 启动前端"
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "===================================="
echo "  后端: http://127.0.0.1:$PORT"
echo "  前端: Electron 窗口已打开"
echo "  停止: kill $BACKEND_PID $FRONTEND_PID"
echo "===================================="

# 等待任意子进程退出
wait
