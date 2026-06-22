"""
最小测试用 MCP 服务器 — 仅供编排层集成测试。

无外部依赖，提供 3 个简单工具用于验证 stdio 连接。
"""

import sys
import os
from pathlib import Path

# 确保 mcp 包可用
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))

from fastmcp import FastMCP

mcp = FastMCP("test-echo")


@mcp.tool()
def echo(message: str) -> str:
    """回声工具 — 原样返回输入消息"""
    return message


@mcp.tool()
def add(a: int, b: int) -> int:
    """加法工具 — 返回两数之和"""
    return a + b


@mcp.tool()
def get_status() -> dict:
    """状态工具 — 返回服务器状态信息"""
    return {
        "status": "ok",
        "server": "test-echo",
        "tools_count": 3,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
