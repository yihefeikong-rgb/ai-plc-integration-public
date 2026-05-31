"""
桌面控制 MCP Server
控制你的电脑鼠标键盘 + 屏幕截图

⚠️ 注意：
- 需要管理员权限才能控制鼠标键盘（Windows）
- 使用前请确保屏幕不要有敏感信息
- 运行中不要动鼠标，会冲突
"""

import asyncio
import base64
import io
import time
import json
import sys
from typing import Optional

try:
    import pyautogui
    pyautogui.FAILSAFE = True  # 鼠标移到左上角可紧急停止
    pyautogui.PAUSE = 0.5
except ImportError:
    print("请先安装 pyautogui: pip install pyautogui", file=sys.stderr)
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("请先安装 Pillow: pip install Pillow", file=sys.stderr)
    sys.exit(1)

# ─── MCP 协议处理 ───────────────────────────────────


def mcp_send(data: dict):
    """向 MCP 客户端发送 JSON-RPC 消息（stdout）"""
    print(json.dumps(data), flush=True)


def mcp_recv() -> dict:
    """从 stdin 读取 JSON-RPC 请求"""
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line)


async def handle_tool_call(req: dict):
    """处理工具调用"""
    tool_name = req["params"]["name"]
    args = req["params"].get("arguments", {})

    try:
        if tool_name == "screenshot":
            result = await tool_screenshot(args)
        elif tool_name == "click":
            result = await tool_click(args)
        elif tool_name == "double_click":
            result = await tool_double_click(args)
        elif tool_name == "right_click":
            result = await tool_right_click(args)
        elif tool_name == "move_mouse":
            result = await tool_move_mouse(args)
        elif tool_name == "type_text":
            result = await tool_type_text(args)
        elif tool_name == "hotkey":
            result = await tool_hotkey(args)
        elif tool_name == "scroll":
            result = await tool_scroll(args)
        elif tool_name == "drag":
            result = await tool_drag(args)
        elif tool_name == "locate_on_screen":
            result = await tool_locate_on_screen(args)
        elif tool_name == "get_screen_size":
            result = await tool_get_screen_size(args)
        elif tool_name == "mouse_position":
            result = await tool_mouse_position(args)
        elif tool_name == "press_key":
            result = await tool_press_key(args)
        else:
            result = {"error": f"未知工具: {tool_name}"}

        mcp_send({
            "jsonrpc": "2.0",
            "id": req.get("id"),
            "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
        })
    except Exception as e:
        mcp_send({
            "jsonrpc": "2.0",
            "id": req.get("id"),
            "error": {"code": -1, "message": str(e)}
        })


# ─── 工具实现 ──────────────────────────────────────


async def tool_screenshot(args: dict) -> dict:
    """截屏（可指定区域）"""
    region = args.get("region")  # (x, y, w, h)
    if region:
        img = pyautogui.screenshot(region=tuple(region))
    else:
        img = pyautogui.screenshot()

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "success": True,
        "width": img.width,
        "height": img.height,
        "format": "base64_png",
        "data": b64,
        "data_len": len(b64),
    }


async def tool_click(args: dict) -> dict:
    """点击指定坐标"""
    x = args.get("x")
    y = args.get("y")
    button = args.get("button", "left")
    clicks = args.get("clicks", 1)
    interval = args.get("interval", 0.1)

    if x is None or y is None:
        # 点击当前位置
        pyautogui.click(button=button, clicks=clicks, interval=interval)
    else:
        pyautogui.click(x, y, button=button, clicks=clicks, interval=interval)

    return {"success": True, "x": x, "y": y, "button": button}


async def tool_double_click(args: dict) -> dict:
    """双击"""
    x, y = args.get("x"), args.get("y")
    if x is not None and y is not None:
        pyautogui.doubleClick(x, y)
    else:
        pyautogui.doubleClick()
    return {"success": True}


async def tool_right_click(args: dict) -> dict:
    """右键点击"""
    x, y = args.get("x"), args.get("y")
    if x is not None and y is not None:
        pyautogui.rightClick(x, y)
    else:
        pyautogui.rightClick()
    return {"success": True}


async def tool_move_mouse(args: dict) -> dict:
    """移动鼠标到指定位置"""
    x, y = args["x"], args["y"]
    duration = args.get("duration", 0.3)
    pyautogui.moveTo(x, y, duration=duration)
    return {"success": True, "x": x, "y": y}


async def tool_type_text(args: dict) -> dict:
    """输入文字"""
    text = args["text"]
    interval = args.get("interval", 0.05)
    pyautogui.write(text, interval=interval)
    return {"success": True, "text_len": len(text)}


async def tool_hotkey(args: dict) -> dict:
    """按下组合键，如 Ctrl+S、Alt+F4"""
    keys = args.get("keys", [])
    if not keys:
        return {"error": "需要 keys 参数（数组）"}
    pyautogui.hotkey(*keys)
    return {"success": True, "keys": keys}


async def tool_scroll(args: dict) -> dict:
    """滚动鼠标滚轮"""
    amount = args.get("amount", -3)  # 负=向下，正=向上
    x, y = args.get("x"), args.get("y")
    if x is not None and y is not None:
        pyautogui.scroll(amount, x, y)
    else:
        pyautogui.scroll(amount)
    return {"success": True, "amount": amount}


async def tool_drag(args: dict) -> dict:
    """拖拽：从(x1,y1)到(x2,y2)"""
    x1, y1 = args["x1"], args["y1"]
    x2, y2 = args["x2"], args["y2"]
    duration = args.get("duration", 0.5)
    pyautogui.drag(x2 - x1, y2 - y1, duration=duration)
    return {"success": True, "from": [x1, y1], "to": [x2, y2]}


async def tool_locate_on_screen(args: dict) -> dict:
    """在屏幕上查找图片（返回坐标）"""
    image_path = args.get("image_path", "")
    confidence = args.get("confidence", 0.8)
    try:
        pos = pyautogui.locateOnScreen(image_path, confidence=confidence)
        if pos:
            return {
                "found": True,
                "x": pos.left, "y": pos.top,
                "width": pos.width, "height": pos.height,
                "center_x": pos.left + pos.width // 2,
                "center_y": pos.top + pos.height // 2,
            }
        return {"found": False, "message": "未找到匹配的图片"}
    except Exception as e:
        return {"error": str(e)}


async def tool_get_screen_size(args: dict) -> dict:
    """获取屏幕分辨率"""
    w, h = pyautogui.size()
    return {"width": w, "height": h}


async def tool_mouse_position(args: dict) -> dict:
    """获取当前鼠标位置"""
    x, y = pyautogui.position()
    return {"x": x, "y": y}


async def tool_press_key(args: dict) -> dict:
    """按下一个键"""
    key = args.get("key", "")
    presses = args.get("presses", 1)
    pyautogui.press(key, presses=presses)
    return {"success": True, "key": key}


# ─── 主循环 ────────────────────────────────────────


async def main():
    """初始化 + 等待 MCP 请求"""
    # 发送初始化通知
    info = {
        "screen": pyautogui.size(),
        "fg_color_depth": "24bit",
    }
    mcp_send({
        "jsonrpc": "2.0",
        "method": "initialized",
        "params": {"server_info": {"name": "desktop-mcp", "version": "0.1", "info": info}}
    })

    # 工具清单
    tools = [
        {
            "name": "screenshot",
            "description": "截屏。返回 base64 PNG 图片。可指定 region=[x,y,w,h] 截取部分区域。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "[x, y, w, h] 截图区域，不传=全屏",
                    }
                },
            },
        },
        {
            "name": "click",
            "description": "鼠标左键点击指定坐标。如果不传 x/y 则在当前位置点击。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X 坐标"},
                    "y": {"type": "integer", "description": "Y 坐标"},
                    "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                    "clicks": {"type": "integer", "default": 1},
                },
            },
        },
        {
            "name": "double_click",
            "description": "鼠标双击指定位置",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
            },
        },
        {
            "name": "right_click",
            "description": "鼠标右键点击",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
            },
        },
        {
            "name": "move_mouse",
            "description": "移动鼠标到指定位置",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "duration": {"type": "number", "default": 0.3},
                },
                "required": ["x", "y"],
            },
        },
        {
            "name": "type_text",
            "description": "在当前焦点处输入文字",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "interval": {"type": "number", "default": 0.05},
                },
                "required": ["text"],
            },
        },
        {
            "name": "hotkey",
            "description": "按下快捷键组合。例如 Ctrl+S: keys=['ctrl','s']；Alt+F4: keys=['alt','f4']",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "按键列表，如 ['ctrl', 's']",
                    }
                },
                "required": ["keys"],
            },
        },
        {
            "name": "scroll",
            "description": "滚动鼠标滚轮。负值=向下滚，正值=向上滚。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "amount": {"type": "integer", "default": -3},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
            },
        },
        {
            "name": "get_screen_size",
            "description": "获取屏幕分辨率",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "mouse_position",
            "description": "获取当前鼠标位置",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "press_key",
            "description": "按一个键。按键名参考 pyautogui 支持的 key 名",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "presses": {"type": "integer", "default": 1},
                },
                "required": ["key"],
            },
        },
        {
            "name": "locate_on_screen",
            "description": "在屏幕上查找图片。需要提前保存目标按钮的截图文件。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "模板图片路径"},
                    "confidence": {"type": "number", "default": 0.8},
                },
                "required": ["image_path"],
            },
        },
        {
            "name": "drag",
            "description": "鼠标拖拽：从(x1,y1)到(x2,y2)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "x1": {"type": "integer"}, "y1": {"type": "integer"},
                    "x2": {"type": "integer"}, "y2": {"type": "integer"},
                    "duration": {"type": "number", "default": 0.5},
                },
                "required": ["x1", "y1", "x2", "y2"],
            },
        },
    ]

    # 发送工具列表
    mcp_send({
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {"tools": tools},
    })

    # 主请求循环
    while True:
        req = mcp_recv()
        if req is None:
            break

        method = req.get("method")

        if method == "tools/list":
            mcp_send({
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "result": {"tools": tools},
            })

        elif method == "tools/call":
            await handle_tool_call(req)

        elif method == "shutdown":
            break


if __name__ == "__main__":
    asyncio.run(main())
