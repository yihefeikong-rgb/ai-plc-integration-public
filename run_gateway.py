"""
已弃用 — 请使用 edge-gateway/src/app.py。

替代命令:
    python -m edge-gateway.src.app

保留此文件仅为防止 import 报错，将在下一版本删除。
"""
import sys
import subprocess

if __name__ == "__main__":
    print("⚠ run_gateway.py 已弃用，请使用: python -m edge-gateway.src.app")
    # 自动重定向到新的 app.py
    cmd = [sys.executable, "-m", "edge-gateway.src.app"] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
