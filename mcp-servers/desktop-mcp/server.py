"""
桌面控制 MCP Server
控制你的电脑鼠标键盘 + 屏幕截图

⚠️ 注意：
- 需要管理员权限才能控制鼠标键盘（Windows）
- 使用前请确保屏幕不要有敏感信息
- 运行中不要动鼠标，会冲突
- 必须设置 MCP_AUTH_TOKEN 环境变量，未设置时拒绝所有工具调用（fail-closed）
"""

import asyncio
import base64
import hmac
import io
import math
import os
import time
import json
import sys
import traceback
from typing import Optional

# ─── 认证 ────────────────────────────────────────────
_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")


def _require_auth(args: dict) -> str | None:
    """验证请求中的 auth_token，返回 None 表示通过，否则返回错误消息

    fail-closed：未配置 MCP_AUTH_TOKEN 时拒绝一切工具调用，不允许默认放行。
    使用 hmac.compare_digest 恒定时间比较，避免时序侧信道。
    """
    if not _AUTH_TOKEN:
        return "认证未启用：服务端必须设置 MCP_AUTH_TOKEN 环境变量，拒绝所有工具调用"
    token = args.get("auth_token", "")
    if not isinstance(token, str):
        return "认证失败：无效的 auth_token"
    # hmac.compare_digest 对非 ASCII str 会抛 TypeError（未捕获将导致进程崩溃），
    # 统一转 UTF-8 字节再比较：任意 str 内容安全且保持恒定时间比较语义。
    if not hmac.compare_digest(token.encode("utf-8"), _AUTH_TOKEN.encode("utf-8")):
        return "认证失败：无效的 auth_token"
    return None


# ─── 按键黑名单（危险快捷键）─────────────────────────
# 黑名单统一使用 pyautogui 规范键名；匹配前做别名归一化与排序，
# 且危险组合附加其他按键（超集）同样拦截，防止顺序重排/别名绕过。
HOTKEY_BLACKLIST = {
    # 系统级危险操作
    ("ctrl", "alt", "delete"),
    ("alt", "f4"),
    # Windows 系统操作
    ("win", "l"),         # 锁屏
    ("win", "r"),         # 运行
    ("win", "d"),         # 显示桌面（暴露其他窗口）
    ("win", "e"),         # 打开资源管理器
    ("alt", "tab"),       # 切换窗口（可能切到敏感窗口）
    ("ctrl", "shift", "esc"),   # 打开任务管理器
    # 格式化/删除类
    ("ctrl", "shift", "delete"),
    # 关机类
    ("alt", "shift", "f4"),
}

# pyautogui 按键别名 → 规范键名
HOTKEY_KEY_ALIASES = {
    "win": "win", "windows": "win", "winleft": "win", "winright": "win",
    "lwin": "win", "rwin": "win", "cmd": "win", "command": "win", "super": "win",
    "ctrl": "ctrl", "control": "ctrl", "ctrlleft": "ctrl", "ctrlright": "ctrl",
    "alt": "alt", "option": "alt", "altleft": "alt", "altright": "alt",
    "shift": "shift", "shiftleft": "shift", "shiftright": "shift",
    "del": "delete", "delete": "delete",
    "esc": "esc", "escape": "esc",
    "enter": "enter", "return": "enter",
}


def _normalize_hotkey_key(k) -> str:
    """归一化单个按键：仅接受字符串并映射别名；非法输入返回空串（一律拒绝）"""
    if not isinstance(k, str):
        return ""
    name = k.lower().strip()
    return HOTKEY_KEY_ALIASES.get(name, name)


def _is_blacklisted_hotkey(keys) -> bool:
    """检查按键组合是否在黑名单中（别名归一化、顺序无关、危险组合超集拦截）

    单键热键与 press_key 等价，必须同样受 PRESS_KEY_BLACKLIST 约束，
    防止 hotkey(keys=["delete"])/["f2"] 绕过单键危险键黑名单。
    """
    normalized = [_normalize_hotkey_key(k) for k in keys]
    if not normalized or any(k == "" for k in normalized):
        return True  # 空组合或含非字符串按键一律拒绝
    pressed = set(normalized)
    # 任何危险单键（含带修饰键的组合，如 shift+delete 的 Windows 永久删除）一律拒绝，
    # 不能因组合长度 >1 绕过单键黑名单。
    if pressed & PRESS_KEY_BLACKLIST:
        return True
    for combo in HOTKEY_BLACKLIST:
        if set(combo).issubset(pressed):
            return True
    return False


# ─── 危险单键黑名单 ──────────────────────────────────
PRESS_KEY_BLACKLIST = {
    "delete", "del",          # 删除文件/内容
    "f2",                     # 重命名（桌面上下文可误操作）
}


def _is_blacklisted_press_key(key) -> bool:
    """检查单键是否在危险黑名单中；非字符串输入一律视为危险"""
    if not isinstance(key, str):
        return True
    return key.lower().strip() in PRESS_KEY_BLACKLIST


# ─── 安全策略拒绝异常 ──────────────────────────────
class ToolRejectedError(Exception):
    """工具被安全策略（黑名单等）拒绝时抛出。

    回送 JSON-RPC error 而不是塞进成功 result，避免客户端把“被拒绝”
    误判为“已执行”；与认证(-2)/确认门(-3) 的失败语义保持一致。
    """


# ─── 危险操作确认门（互锁）───────────────────────────
# 可注入按键或移动窗口的控制操作必须显式携带 confirm=true 才允许执行，
# 缺省拒绝（fail-closed），防止未确认的自动控制链。
DANGEROUS_TOOLS = {"type_text", "hotkey", "press_key", "drag", "click", "double_click", "right_click"}


def _require_confirmation(tool_name: str, args: dict) -> str | None:
    """危险工具必须显式确认，返回 None 表示通过，否则返回错误消息"""
    if tool_name in DANGEROUS_TOOLS and args.get("confirm") is not True:
        return f"危险操作 {tool_name} 需要 confirm=true 显式确认"
    return None


def _audit(message: str):
    """最小审计日志（stderr）：仅记录事件，不记录参数值/令牌"""
    print(f"[audit] {time.strftime('%Y-%m-%d %H:%M:%S')} {message}", file=sys.stderr)


def _to_int(value, name: str, default=None, required: bool = False):
    """校验并转换整数参数；非法值抛 ValueError（消息不含内部细节）"""
    if value is None:
        if required:
            raise ValueError(f"缺少必填参数 {name}")
        return default
    if isinstance(value, bool):
        raise ValueError(f"参数 {name} 必须是整数")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"参数 {name} 必须是整数，实际类型: {type(value).__name__}")


def _to_float(value, name: str, default=None, required: bool = False):
    """校验并转换浮点参数；非法值抛 ValueError（消息不含内部细节）"""
    if value is None:
        if required:
            raise ValueError(f"缺少必填参数 {name}")
        return default
    if isinstance(value, bool):
        raise ValueError(f"参数 {name} 必须是数字")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"参数 {name} 必须是数字，实际类型: {type(value).__name__}")
    # NaN/±Infinity 不是合法控制参数（可经 JSON 的 NaN/Infinity 或字符串注入），
    # 会绕过常规比较并让 time.sleep 等调用异常，一律拒绝（fail-closed）
    if not math.isfinite(result):
        raise ValueError(f"参数 {name} 必须是有限数字")
    return result

try:
    import pyautogui
    pyautogui.FAILSAFE = True  # 鼠标移到左上角可紧急停止
    pyautogui.PAUSE = 0.1  # 保持 pyautogui 默认节流，避免每个调用额外 0.5s 固定延迟
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
    try:
        print(json.dumps(data), flush=True)
    except (BrokenPipeError, OSError):
        # 客户端已断开：优雅退出，不向上抛未处理异常
        sys.exit(0)


def _reject_nonstandard_constant(name: str):
    """json.loads 的 parse_constant：拒绝 NaN/Infinity，严格 JSON，fail-closed"""
    raise ValueError(f"非标准 JSON 常量: {name}")


# 解析失败哨兵：按对象同一性判断，与任何合法 JSON-RPC 请求的顶层键都不可能冲突
_PARSE_ERROR = object()


def mcp_recv() -> dict | None:
    """从 stdin 读取 JSON-RPC 请求

    EOF 返回 None；非法 JSON 或非对象请求返回 _PARSE_ERROR 哨兵，
    由主循环回送 JSON-RPC parse error，避免单行坏数据杀死整个服务器。
    """
    try:
        line = sys.stdin.readline()
    except OSError:
        return None
    if not line:
        return None
    try:
        data = json.loads(line, parse_constant=_reject_nonstandard_constant)
    except UnicodeDecodeError:
        # 非法 UTF-8 字节：返回 parse error 哨兵，绝不杀死整个服务器进程
        return _PARSE_ERROR
    except (json.JSONDecodeError, ValueError, RecursionError):
        # 非法 JSON / 深度嵌套 JSON：返回 parse error 哨兵，避免单行坏数据崩溃
        return _PARSE_ERROR
    if not isinstance(data, dict):
        return _PARSE_ERROR
    return data


async def handle_tool_call(req: dict):
    """处理工具调用"""
    req_id = req.get("id")
    params = req.get("params")
    if not isinstance(params, dict):
        mcp_send({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32602, "message": "无效请求：params 必须是 JSON 对象"}
        })
        return
    tool_name = params.get("name")
    args = params.get("arguments", {})
    if not isinstance(tool_name, str) or not isinstance(args, dict):
        mcp_send({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32602, "message": "无效请求：name 必须是字符串，arguments 必须是 JSON 对象"}
        })
        return

    # 认证检查（fail-closed：未配置 MCP_AUTH_TOKEN 时拒绝一切调用）
    auth_err = _require_auth(args)
    if auth_err:
        _audit(f"auth_rejected tool={tool_name}")
        mcp_send({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -2, "message": auth_err}
        })
        return

    # 危险操作确认门（互锁）
    confirm_err = _require_confirmation(tool_name, args)
    if confirm_err:
        _audit(f"confirm_rejected tool={tool_name}")
        mcp_send({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -3, "message": confirm_err}
        })
        return

    try:
        _audit(f"tool={tool_name}")

        if tool_name == "screenshot":
            result = await asyncio.to_thread(tool_screenshot, args)
        elif tool_name == "click":
            result = await asyncio.to_thread(tool_click, args)
        elif tool_name == "double_click":
            result = await asyncio.to_thread(tool_double_click, args)
        elif tool_name == "right_click":
            result = await asyncio.to_thread(tool_right_click, args)
        elif tool_name == "move_mouse":
            result = await asyncio.to_thread(tool_move_mouse, args)
        elif tool_name == "type_text":
            result = await asyncio.to_thread(tool_type_text, args)
        elif tool_name == "hotkey":
            result = await asyncio.to_thread(tool_hotkey, args)
        elif tool_name == "scroll":
            result = await asyncio.to_thread(tool_scroll, args)
        elif tool_name == "drag":
            result = await asyncio.to_thread(tool_drag, args)
        elif tool_name == "locate_on_screen":
            result = await asyncio.to_thread(tool_locate_on_screen, args)
        elif tool_name == "get_screen_size":
            result = await asyncio.to_thread(tool_get_screen_size, args)
        elif tool_name == "mouse_position":
            result = await asyncio.to_thread(tool_mouse_position, args)
        elif tool_name == "press_key":
            result = await asyncio.to_thread(tool_press_key, args)
        else:
            result = {"error": f"未知工具: {tool_name}"}

        mcp_send({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
        })
    except ToolRejectedError as e:
        # 安全策略拒绝（黑名单）：回送 JSON-RPC error，与认证/确认门失败语义一致
        _audit(f"rejected tool={tool_name}")
        mcp_send({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -4, "message": str(e)}
        })
    except ValueError as e:
        # 输入校验类错误：消息由代码生成且不含内部细节，可安全回传
        mcp_send({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -1, "message": str(e)}
        })
    except Exception:
        # 兜底：不向客户端泄露路径、库内部细节或回显输入内容
        traceback.print_exc(file=sys.stderr)
        mcp_send({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -1, "message": "工具执行失败，请检查服务端日志"}
        })


# ─── 工具实现 ──────────────────────────────────────


def tool_screenshot(args: dict) -> dict:
    """截屏（可指定区域）

    ⚠️ 安全警告: 截图可能包含敏感信息（密码、令牌、个人数据）。
    返回数据中包含 sensitivity_warning 字段提醒调用方。
    """
    region = args.get("region")  # (x, y, w, h)
    if region is not None:
        if not isinstance(region, (list, tuple)) or len(region) != 4:
            raise ValueError("参数 region 必须是 [x, y, w, h] 四元素数组")
        img = pyautogui.screenshot(region=tuple(_to_int(v, "region 元素", required=True) for v in region))
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
        "sensitivity_warning": "截图可能包含敏感信息，请勿存储或转发至不可信目标",
    }


def tool_click(args: dict) -> dict:
    """点击指定坐标（危险操作，需 confirm=true）"""
    x = _to_int(args.get("x"), "x")
    y = _to_int(args.get("y"), "y")
    if (x is None) != (y is None):
        raise ValueError("参数 x 和 y 必须同时提供或同时省略")
    button = args.get("button", "left")
    if not isinstance(button, str) or button not in ("left", "right", "middle"):
        raise ValueError("参数 button 必须是 left/right/middle 之一")
    clicks = _to_int(args.get("clicks"), "clicks", 1)
    if clicks < 1:
        raise ValueError("参数 clicks 必须 >= 1")
    interval = _to_float(args.get("interval"), "interval", 0.1)
    if interval < 0:
        raise ValueError("参数 interval 必须 >= 0")

    if x is None or y is None:
        # 点击当前位置
        pyautogui.click(button=button, clicks=clicks, interval=interval)
    else:
        pyautogui.click(x, y, button=button, clicks=clicks, interval=interval)

    return {"success": True, "x": x, "y": y, "button": button}


def tool_double_click(args: dict) -> dict:
    """双击（危险操作，需 confirm=true）"""
    x = _to_int(args.get("x"), "x")
    y = _to_int(args.get("y"), "y")
    if (x is None) != (y is None):
        raise ValueError("参数 x 和 y 必须同时提供或同时省略")
    if x is not None and y is not None:
        pyautogui.doubleClick(x, y)
    else:
        pyautogui.doubleClick()
    return {"success": True, "x": x, "y": y}


def tool_right_click(args: dict) -> dict:
    """右键点击（危险操作，需 confirm=true）"""
    x = _to_int(args.get("x"), "x")
    y = _to_int(args.get("y"), "y")
    if (x is None) != (y is None):
        raise ValueError("参数 x 和 y 必须同时提供或同时省略")
    if x is not None and y is not None:
        pyautogui.rightClick(x, y)
    else:
        pyautogui.rightClick()
    return {"success": True, "x": x, "y": y}


def tool_move_mouse(args: dict) -> dict:
    """移动鼠标到指定位置"""
    x = _to_int(args.get("x"), "x", required=True)
    y = _to_int(args.get("y"), "y", required=True)
    duration = _to_float(args.get("duration"), "duration", 0.3)
    pyautogui.moveTo(x, y, duration=duration)
    return {"success": True, "x": x, "y": y}


def tool_type_text(args: dict) -> dict:
    """输入文字（危险操作，需 confirm=true）"""
    text = args.get("text")
    if not isinstance(text, str) or not text:
        raise ValueError("参数 text 必须是非空字符串")
    interval = _to_float(args.get("interval"), "interval", 0.05)
    if interval < 0:
        raise ValueError("参数 interval 必须 >= 0")
    pyautogui.write(text, interval=interval)
    return {"success": True, "text_len": len(text)}


def tool_hotkey(args: dict) -> dict:
    """按下组合键，如 Ctrl+S（危险操作，需 confirm=true）"""
    keys = args.get("keys", [])
    if not isinstance(keys, list) or not keys:
        raise ValueError("需要 keys 参数（字符串数组）")
    if _is_blacklisted_hotkey(keys):
        raise ToolRejectedError(f"按键组合 {keys} 在黑名单中，禁止执行（危险操作）")
    pyautogui.hotkey(*keys)
    return {"success": True, "keys": keys}


def tool_scroll(args: dict) -> dict:
    """滚动鼠标滚轮"""
    amount = _to_int(args.get("amount"), "amount", -3)  # 负=向下，正=向上
    x = _to_int(args.get("x"), "x")
    y = _to_int(args.get("y"), "y")
    if (x is None) != (y is None):
        raise ValueError("参数 x 和 y 必须同时提供或同时省略")
    if x is not None and y is not None:
        pyautogui.scroll(amount, x, y)
    else:
        pyautogui.scroll(amount)
    return {"success": True, "amount": amount}


def tool_drag(args: dict) -> dict:
    """拖拽：从(x1,y1)到(x2,y2)（危险操作，需 confirm=true）"""
    x1 = _to_int(args.get("x1"), "x1", required=True)
    y1 = _to_int(args.get("y1"), "y1", required=True)
    x2 = _to_int(args.get("x2"), "x2", required=True)
    y2 = _to_int(args.get("y2"), "y2", required=True)
    duration = _to_float(args.get("duration"), "duration", 0.5)
    # 先移动到起点再拖拽，保证“从(x1,y1)到(x2,y2)”的起点语义
    pyautogui.moveTo(x1, y1)
    pyautogui.dragTo(x2, y2, duration=duration)
    return {"success": True, "from": [x1, y1], "to": [x2, y2]}


def tool_locate_on_screen(args: dict) -> dict:
    """在屏幕上查找图片（返回坐标）"""
    image_path = args.get("image_path")
    if not isinstance(image_path, str) or not image_path:
        raise ValueError("参数 image_path 必须是非空字符串")
    if "\x00" in image_path:
        raise ValueError("参数 image_path 非法")
    confidence = _to_float(args.get("confidence"), "confidence", 0.8)
    if not (0 < confidence <= 1):
        raise ValueError("参数 confidence 必须在 (0, 1] 范围内")
    region = args.get("region")
    if region is not None:
        if not isinstance(region, (list, tuple)) or len(region) != 4:
            raise ValueError("参数 region 必须是 [x, y, w, h] 四元素数组")
        region = tuple(_to_int(v, "region 元素", required=True) for v in region)
    try:
        if region:
            pos = pyautogui.locateOnScreen(image_path, confidence=confidence, region=region)
        else:
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
    except Exception:
        # 不向客户端泄露 image_path / 库内部细节；详细原因只进 stderr 日志
        traceback.print_exc(file=sys.stderr)
        raise ValueError("查找图片失败（请检查 image_path 是否存在且格式受支持）")


def tool_get_screen_size(args: dict) -> dict:
    """获取屏幕分辨率"""
    w, h = pyautogui.size()
    return {"width": w, "height": h}


def tool_mouse_position(args: dict) -> dict:
    """获取当前鼠标位置"""
    x, y = pyautogui.position()
    return {"x": x, "y": y}


def tool_press_key(args: dict) -> dict:
    """按下一个键（危险操作，需 confirm=true）"""
    key = args.get("key")
    if not isinstance(key, str) or not key:
        raise ValueError("参数 key 必须是非空字符串")
    presses = _to_int(args.get("presses"), "presses", 1)
    if presses < 1:
        raise ValueError("参数 presses 必须 >= 1")
    if _is_blacklisted_press_key(key):
        raise ToolRejectedError(f"按键 '{key}' 在危险黑名单中，禁止执行（可能导致数据丢失）")
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
            "description": "鼠标左键点击指定坐标。如果不传 x/y 则在当前位置点击。危险操作：需 confirm=true 显式确认",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X 坐标"},
                    "y": {"type": "integer", "description": "Y 坐标"},
                    "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                    "clicks": {"type": "integer", "default": 1},
                    "confirm": {"type": "boolean", "description": "危险操作，必须显式置为 true"},
                },
                "required": ["confirm"],
            },
        },
        {
            "name": "double_click",
            "description": "鼠标双击指定位置。危险操作：需 confirm=true 显式确认",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "confirm": {"type": "boolean", "description": "危险操作，必须显式置为 true"},
                },
                "required": ["confirm"],
            },
        },
        {
            "name": "right_click",
            "description": "鼠标右键点击。危险操作：需 confirm=true 显式确认",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "confirm": {"type": "boolean", "description": "危险操作，必须显式置为 true"},
                },
                "required": ["confirm"],
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
            "description": "在当前焦点处输入文字。危险操作：需 confirm=true 显式确认",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "interval": {"type": "number", "default": 0.05},
                    "confirm": {"type": "boolean", "description": "危险操作，必须显式置为 true"},
                },
                "required": ["text", "confirm"],
            },
        },
        {
            "name": "hotkey",
            "description": "按下快捷键组合。例如 Ctrl+S: keys=['ctrl','s']。危险操作：需 confirm=true 显式确认；Alt+F4/锁屏等系统级组合被黑名单拦截",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "按键列表，如 ['ctrl', 's']",
                    },
                    "confirm": {"type": "boolean", "description": "危险操作，必须显式置为 true"},
                },
                "required": ["keys", "confirm"],
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
            "description": "按一个键。按键名参考 pyautogui 支持的 key 名。危险操作：需 confirm=true 显式确认",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "presses": {"type": "integer", "default": 1},
                    "confirm": {"type": "boolean", "description": "危险操作，必须显式置为 true"},
                },
                "required": ["key", "confirm"],
            },
        },
        {
            "name": "locate_on_screen",
            "description": "在屏幕上查找图片。需要提前保存目标按钮的截图文件。可指定 region=[x,y,w,h] 只搜索局部区域",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "模板图片路径"},
                    "confidence": {"type": "number", "default": 0.8},
                    "region": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "[x, y, w, h] 搜索区域，不传=全屏",
                    },
                },
                "required": ["image_path"],
            },
        },
        {
            "name": "drag",
            "description": "鼠标拖拽：从(x1,y1)到(x2,y2)。危险操作：需 confirm=true 显式确认",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "x1": {"type": "integer"}, "y1": {"type": "integer"},
                    "x2": {"type": "integer"}, "y2": {"type": "integer"},
                    "duration": {"type": "number", "default": 0.5},
                    "confirm": {"type": "boolean", "description": "危险操作，必须显式置为 true"},
                },
                "required": ["x1", "y1", "x2", "y2", "confirm"],
            },
        },
    ]

    # 工具列表响应体预构建，复用避免重复序列化
    tools_result = {"tools": tools}

    # 发送工具列表
    mcp_send({
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": tools_result,
    })

    # 主请求循环
    while True:
        req = mcp_recv()
        if req is None:
            break

        if req is _PARSE_ERROR:
            mcp_send({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            })
            continue

        method = req.get("method")

        if method == "tools/list":
            mcp_send({
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "result": tools_result,
            })

        elif method == "tools/call":
            await handle_tool_call(req)

        elif method == "shutdown":
            break

        else:
            # 未知方法（含标准 MCP initialize 等）：回送明确错误，避免客户端挂起
            mcp_send({
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })


if __name__ == "__main__":
    asyncio.run(main())
