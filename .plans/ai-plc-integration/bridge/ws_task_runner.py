#!/usr/bin/env python3
"""
ws_task_runner.py — cc-haha 受控 WS 任务投递 MVP (C-14)

职责：
  1. 复用 check_sidecar.py 端口发现
  2. POST /api/sessions 创建会话
  3. WS /ws/{sessionId} 建立连接
  4. 发送 user_message 投递任务
  5. 处理 permission_request（保守策略）
  6. 等待 message_complete
  7. 回填 claude_result.md + 切 state.json → NEED_CODEX_REVIEW

只读约束：
  - 不修改 sidecar 状态
  - 不修改业务代码
  - 不自动 review/git/重试

保守权限策略：
  - 自动拒绝：文件写入、命令执行、未知工具、高风险权限
  - 拒绝后记录权限请求并结束到可审查状态

用法：
  D:/Python3/python.exe ws_task_runner.py "你的任务描述"
  D:/Python3/python.exe ws_task_runner.py "生成一个三相电机正反转 SCL 程序" --timeout 300
"""

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import websocket

# ── 路径 ──────────────────────────────────────────────────
BRIDGE_DIR = Path(__file__).parent
STATE_FILE = BRIDGE_DIR / "state.json"
RUNS_DIR = BRIDGE_DIR / "runs"
PROJECT_ROOT = BRIDGE_DIR.resolve().parents[2]
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

from bridge_state import (
    BridgeStateError,
    artifact_sha256,
    locked_state,
    read_state,
    write_text_atomic,
)

# ── 默认配置 ─────────────────────────────────────────────
DEFAULT_TIMEOUT = 180        # 总超时（秒）
WS_MSG_TIMEOUT = 15          # 单条 WS 消息超时（秒）
SESSION_CREATE_TIMEOUT = 10  # REST 建会话超时
SESSION_PERMISSION_MODE = "default"
MAX_RETAINED_OUTPUT_CHARS = 20_000
_SENSITIVE_OUTPUT_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret|authorization)\b(\s*[:=]\s*)([^\s`'\"|,;]+)"
)

# ── 高危工具名/关键词（触发自动拒绝）─────────────────────
HIGH_RISK_TOOL_PATTERNS = [
    "write", "create", "delete", "remove", "update",
    "bash", "shell", "exec", "run", "command",
    "fs_write", "filesystem", "file_write",
    "computer", "screenshot", "keyboard", "mouse",
    "s7_write", "plc_write", "download",
]
UNKNOWN_TOOL_RISK = True  # 不在白名单的工具视为高风险
READ_ONLY_TOOL_PATH_FIELDS = {
    "read": ("file_path", "path"),
    "ls": ("path",),
    "glob": ("path",),
    "grep": ("path",),
}


def _retain_safe_output(value: object) -> str:
    """保留有限、可审查的 Claude 正文，同时去除明显密钥值。"""
    if isinstance(value, list):
        text = "".join(str(item) for item in value)
    elif value is None:
        text = ""
    else:
        text = str(value)
    text = "".join(char if char.isprintable() or char in "\n\r\t" else "?" for char in text)
    text = _SENSITIVE_OUTPUT_VALUE.sub(r"\1\2[REDACTED]", text)
    if len(text) > MAX_RETAINED_OUTPUT_CHARS:
        return text[:MAX_RETAINED_OUTPUT_CHARS] + "\n\n[TRUNCATED: retained output limit reached]"
    return text


def _log(msg: str):
    """带时间戳的日志"""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def generate_run_id(task_name: str) -> str:
    """生成 run_id：{YYYYMMDD}_{HHMMSS}_{ffffff}_{task_slug}"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    slug = re.sub(r'[^a-z0-9]+', '-', task_name.lower())[:30]
    slug = slug.strip('-')
    return f"{ts}_{slug}" if slug else ts


def ensure_run_dir(task_name: str) -> tuple[Path, str]:
    """每次执行生成新的 runs/{run_id}/ 子目录，返回 (run_dir, run_id)

    不复用 state.json 中的旧 run_id——每次调用 = 新一轮 = 新目录。
    """
    run_id = generate_run_id(task_name)
    _log(f"[RUN] 新 run_id: {run_id}")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, run_id


def _is_high_risk(tool_name: str, tool_input: dict) -> tuple[bool, str]:
    """判断工具权限请求是否为高风险

    规则：
      1. 无工具名 → 高风险（未知工具）
      2. 工具名匹配高危模式 → 高风险
      3. UNKNOWN_TOOL_RISK=True 时，所有不在白名单的工具 → 高风险
      4. 否则 → 低风险
    """
    if not tool_name:
        return True, "unknown tool (no name)"

    name_lower = tool_name.lower()
    for pattern in HIGH_RISK_TOOL_PATTERNS:
        if pattern in name_lower:
            return True, f"tool '{tool_name}' matches risk pattern '{pattern}'"

    if UNKNOWN_TOOL_RISK:
        return True, f"unknown tool '{tool_name}' denied by conservative policy"

    return False, ""


def _resolve_tool_path(path_value: str) -> Path:
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve(strict=False)


def _is_within_project_root(path_value: str) -> bool:
    try:
        resolved = _resolve_tool_path(path_value)
        resolved.relative_to(PROJECT_ROOT.resolve(strict=False))
        return True
    except ValueError:
        return False


def decide_permission(tool_name: str, tool_input: dict) -> tuple[bool, str]:
    """决定是否放行权限请求。"""
    if not isinstance(tool_input, dict):
        return False, "invalid tool input"

    name_lower = (tool_name or "").lower()
    path_fields = READ_ONLY_TOOL_PATH_FIELDS.get(name_lower)

    if path_fields:
        for field_name in path_fields:
            field_value = tool_input.get(field_name)
            if isinstance(field_value, str) and field_value.strip():
                if _is_within_project_root(field_value):
                    return True, f"read-only tool '{tool_name}' within project root"
                return False, f"read-only tool '{tool_name}' targets path outside project root"
        return False, f"read-only tool '{tool_name}' missing path field"

    is_risk, risk_reason = _is_high_risk(tool_name, tool_input)
    return (not is_risk, "低风险，自动放行") if not is_risk else (False, risk_reason)


# ── 端口发现（复用 check_sidecar 逻辑）────────────────────


def discover_sidecar() -> dict:
    """三层端口发现：state-file → scan → override"""
    # 尝试从 check_sidecar.py 导入
    try:
        from check_sidecar import (
            layer1_state_file, layer2_scan, layer3_override,
            _gather_seed_ports, _check_health,
        )
    except ImportError:
        # 兜底：内联简化版发现
        return _discover_inline()

    # Layer 1
    r1 = layer1_state_file()
    if r1["found"]:
        health = _check_health(r1["host"], r1["port"])
        if health["health_ok"]:
            return {"found": True, "host": r1["host"], "port": r1["port"],
                    "source": "state-file", "url": f"http://{r1['host']}:{r1['port']}"}

    # Layer 2
    seed = _gather_seed_ports(r1["port"] if r1["found"] else None)
    r2 = layer2_scan(seed_ports=seed)
    if r2["found"]:
        return {"found": True, "host": r2["host"], "port": r2["port"],
                "source": "scan", "url": f"http://{r2['host']}:{r2['port']}"}

    # Layer 3
    r3 = layer3_override()
    if r3["found"]:
        return {"found": True, "host": r3["host"], "port": r3["port"],
                "source": "override", "url": f"http://{r3['host']}:{r3['port']}"}

    return {"found": False, "error": "三层发现均未找到 sidecar"}


def _discover_inline() -> dict:
    """内联简化端口发现（check_sidecar.py 不可用时兜底）"""
    import socket as sock
    state_file = Path.home() / ".claude" / "desktop-server-state.json"
    candidates = [3456, 3457, 3458, 3449, 3460, 8080, 3000, 5173]

    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            port = data.get("lastPort")
            if port and isinstance(port, int):
                candidates.insert(0, port)
                for offset in range(1, 11):
                    if port + offset <= 65535:
                        candidates.append(port + offset)
                    if port - offset >= 1:
                        candidates.append(port - offset)
        except (json.JSONDecodeError, OSError):
            pass

    host = "127.0.0.1"
    for port in candidates[:40]:
        try:
            with sock.create_connection((host, port), timeout=1):
                # TCP 通后还要验证 /health
                try:
                    req = Request(f"http://{host}:{port}/health", method="GET")
                    with urlopen(req, timeout=HEALTH_TIMEOUT) as resp:
                        if resp.status == 200:
                            _log(f"[OK] inline-scan found sidecar at {host}:{port}")
                            return {"found": True, "host": host, "port": port,
                                    "source": "inline-scan",
                                    "url": f"http://{host}:{port}"}
                except Exception:
                    continue
        except (OSError, sock.timeout):
            continue
    return {"found": False, "error": "内联扫描未找到 sidecar"}


# ── REST 会话创建 ────────────────────────────────────────


def create_session(
    base_url: str,
    timeout: int = SESSION_CREATE_TIMEOUT,
    work_dir: str | Path | None = None,
    permission_mode: str = SESSION_PERMISSION_MODE,
) -> dict:
    """POST /api/sessions → 创建 Claude 会话"""
    url = f"{base_url}/api/sessions"
    session_work_dir = str(work_dir or PROJECT_ROOT)
    body = json.dumps({
        "workDir": session_work_dir,
        "permissionMode": permission_mode,
    }).encode("utf-8")
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            session_id = data.get("id") or data.get("sessionId")
            if not session_id:
                return {"ok": False, "error": f"返回体无会话 ID: {json.dumps(data)[:200]}", "raw": data}
            return {
                "ok": True,
                "session_id": session_id,
                "work_dir": session_work_dir,
                "permission_mode": permission_mode,
                "raw": data,
            }
    except HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8')[:200]}"}
    except URLError as e:
        return {"ok": False, "error": f"连接失败: {e.reason}"}
    except (OSError, json.JSONDecodeError) as e:
        return {"ok": False, "error": f"异常: {e}"}


def get_session_metadata(base_url: str, session_id: str, timeout: int = SESSION_CREATE_TIMEOUT) -> dict:
    """回读 sidecar 会话元数据；无法证明 CWD/权限模式时禁止复用。"""
    if not session_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
        return {"ok": False, "error": "session_id 格式无效"}
    url = f"{base_url}/api/sessions/{session_id}"
    try:
        with urlopen(Request(url, method="GET"), timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        return {"ok": False, "error": f"session metadata HTTP {exc.code}"}
    except (URLError, OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"session metadata unavailable: {exc}"}

    work_dir = data.get("workDir") or data.get("work_dir") or data.get("cwd")
    permission_mode = data.get("permissionMode") or data.get("permission_mode")
    if not isinstance(work_dir, str) or not work_dir:
        return {"ok": False, "error": "session metadata 缺少 workDir", "raw": data}
    if not isinstance(permission_mode, str) or not permission_mode:
        return {"ok": False, "error": "session metadata 缺少 permissionMode", "raw": data}
    if not _is_project_root(work_dir):
        return {"ok": False, "error": f"session CWD 漂移: {work_dir}", "raw": data}
    if permission_mode != SESSION_PERMISSION_MODE:
        return {
            "ok": False,
            "error": f"session permissionMode 不符合受控策略: {permission_mode}",
            "raw": data,
        }
    return {
        "ok": True,
        "session_id": session_id,
        "work_dir": str(Path(work_dir).resolve(strict=False)),
        "permission_mode": permission_mode,
        "verified": True,
        "raw": data,
    }


def resolve_session(
    base_url: str,
    reuse_session_id: str = "",
    timeout: int = SESSION_CREATE_TIMEOUT,
) -> dict:
    """创建或复用 session 后必须回读并核验其 CWD 与权限模式。"""
    if reuse_session_id:
        session = get_session_metadata(base_url, reuse_session_id, timeout=timeout)
        session["reused"] = True
        session["metadata_checked"] = True
        return session

    created = create_session(base_url, timeout=timeout)
    if not created.get("ok"):
        created["reused"] = False
        return created

    session_id = created.get("session_id", "")
    session = get_session_metadata(base_url, session_id, timeout=timeout)
    session["reused"] = False
    session["metadata_checked"] = True
    if not session.get("ok"):
        session["error"] = f"created session metadata was not verified: {session.get('error', '?')}"
    return session


def _is_project_root(path_value: str) -> bool:
    try:
        return _resolve_tool_path(path_value) == PROJECT_ROOT.resolve(strict=False)
    except (OSError, TypeError, ValueError):
        return False


def _stop_rule(code: str, reason: str, stop: bool = True) -> dict:
    return {
        "code": code,
        "stop": stop,
        "reason": reason,
    }


def classify_stop_rule(sidecar_info: dict, session_info: dict | None, session_result: dict) -> dict:
    """统一分类受控 runner 必须停住并等待人工审查的原因。"""
    if not sidecar_info.get("found"):
        return _stop_rule(
            "SIDECAR_UNAVAILABLE",
            f"sidecar unavailable: {sidecar_info.get('error', '?')}",
        )

    if session_info and session_info.get("metadata_checked") and not session_info.get("verified"):
        return _stop_rule(
            "SESSION_METADATA_UNVERIFIED",
            f"session metadata was not verified: {session_info.get('error', '?')}",
        )

    if not session_info or not session_info.get("ok"):
        err = session_info.get("error") if session_info else "session creation not attempted"
        return _stop_rule("SESSION_CREATE_FAILED", f"session creation failed: {err or '?'}")

    work_dir = session_info.get("work_dir", "")
    if work_dir and not _is_project_root(work_dir):
        return _stop_rule("CWD_DRIFT", f"session work_dir is outside project root: {work_dir}")

    error = session_result.get("error") or ""
    if "超时" in error or "timeout" in error.lower():
        return _stop_rule("WS_TIMEOUT", error)

    denied = [p for p in session_result.get("permission_requests", []) if not p.get("allowed")]
    if denied:
        return _stop_rule("PERMISSION_DENIED", f"{len(denied)} permission request(s) denied")

    if session_result.get("ok"):
        return _stop_rule("NONE", "no stop rule triggered", stop=False)

    if error:
        return _stop_rule("SESSION_FAILED", error)

    return _stop_rule("SESSION_INCOMPLETE", "session ended without a successful completion")


# ── WS 事件循环 ──────────────────────────────────────────


def run_ws_session(
    ws_url: str,
    task_text: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """
    WS 事件主循环

    流程：
      1. 等待 'connected' 事件
      2. 发送 'user_message'
      3. 事件循环处理
      4. 超时或 message_complete 收尾
    """
    ws = websocket.create_connection(ws_url, timeout=15)
    ws.settimeout(WS_MSG_TIMEOUT)

    result = {
        "ok": False,
        "session_id": "",
        "events": [],
        "thinking_count": 0,
        "permission_requests": [],
        "output_text": [],
        "usage": {},
        "error": None,
    }

    connected = False
    message_sent = False
    done = False
    start_ts = time.time()

    try:
        while not done and (time.time() - start_ts) < timeout:
            try:
                raw = ws.recv()
                if not raw:
                    continue
            except websocket.WebSocketTimeoutException:
                _log("[WARN] WS 消息超时，仍在等待...")
                continue

            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                result["events"].append({"type": "raw", "data": raw[:200]})
                continue

            event_type = event.get("type", "unknown")
            result["events"].append(event)

            # ── connected ──
            if event_type == "connected":
                connected = True
                result["session_id"] = event.get("sessionId", "")
                _log(f"[WS] connected, sessionId={result['session_id']}")

                # 连接建立后立即投递消息
                user_msg = json.dumps({"type": "user_message", "content": task_text})
                ws.send(user_msg)
                message_sent = True
                _log(f"[WS] user_message sent ({len(task_text)} chars)")

            # ── status ──
            elif event_type == "status":
                state = event.get("state", "")
                verb = event.get("verb", "")
                _log(f"[WS] status: {state}{f' ({verb})' if verb else ''}")

            # ── content_start / content_delta ──
            elif event_type == "content_start":
                pass  # 流开始，无文本内容
            elif event_type == "content_delta":
                text = event.get("text", "")
                if text:
                    result["output_text"].append(text)

            # ── thinking ──
            elif event_type == "thinking":
                result["thinking_count"] += 1
                pass  # 不记入事件日志，汇总计数

            # ── tool_use_complete ──
            elif event_type == "tool_use_complete":
                tool_name = event.get("toolName", "?")
                _log(f"[WS] tool_use_complete: {tool_name}")

            # ── permission_request ──
            elif event_type == "permission_request":
                req_id = event.get("requestId", "")
                tool_name = event.get("toolName", "?")
                tool_input = event.get("input", {})
                description = event.get("description", "")
                _log(f"[WS] permission_request: {tool_name} ({description[:80]})")

                allowed, decision_reason = decide_permission(tool_name, tool_input)

                perm_record = {
                    "requestId": req_id,
                    "toolName": tool_name,
                    "input": tool_input,
                    "description": description,
                    "allowed": allowed,
                    "reason": decision_reason,
                }
                result["permission_requests"].append(perm_record)

                # 发送响应
                resp = json.dumps({
                    "type": "permission_response",
                    "requestId": req_id,
                    "allowed": allowed,
                    "denyMessage": decision_reason if not allowed else "",
                })
                ws.send(resp)

                if allowed:
                    _log(f"  -> ALLOW: {tool_name} ({decision_reason})")
                else:
                    _log(f"  -> DENY: {tool_name} ({decision_reason})")

            # ── message_complete ──
            elif event_type == "message_complete":
                usage = event.get("usage", {})
                result["usage"] = {
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                }
                _log(f"[WS] message_complete (in={result['usage']['input_tokens']}, "
                     f"out={result['usage']['output_tokens']})")
                done = True
                result["ok"] = True

            # ── error ──
            elif event_type == "error":
                err_msg = event.get("message", "?")
                err_code = event.get("code", "?")
                result["error"] = f"[{err_code}] {err_msg}"
                _log(f"[WS] ERROR: {result['error']}")
                done = True
                result["ok"] = False

            # ── other ──
            elif event_type == "pong":
                pass
            else:
                _log(f"[WS] unhandled event: {event_type}")

        # ── 循环结束 ──
        elapsed = round(time.time() - start_ts, 1)

        if not connected:
            result["error"] = "未收到 connected 事件，WS 连接可能无效"
            result["ok"] = False
        elif not message_sent:
            result["error"] = "连接已建立但未发送 user_message"
            result["ok"] = False
        elif not result.get("ok") and not result.get("error"):
            if (time.time() - start_ts) >= timeout:
                result["error"] = f"超时 ({timeout}s)"
            else:
                result["error"] = "会话异常结束"
        elif result.get("ok"):
            result["output_text"] = "".join(result["output_text"])

        result["elapsed"] = elapsed
        return result

    except websocket.WebSocketException as e:
        return {**result, "ok": False, "error": f"WS 异常: {e}", "elapsed": round(time.time() - start_ts, 1)}
    except Exception as e:
        return {**result, "ok": False, "error": f"异常: {e}", "elapsed": round(time.time() - start_ts, 1)}
    finally:
        try:
            ws.close()
        except Exception:
            pass


# ── Bridge 文件回填 ──────────────────────────────────────


def write_claude_result(sidecar_info: dict, session_result: dict, task_text: str,
                        session_info: dict | None = None, elapsed: float = 0,
                        run_dir: Path | None = None):
    """Write claude_result.md - always called, even on failure"""
    summary = "unknown"
    perms = session_result.get("permission_requests", [])
    denied = [p for p in perms if not p["allowed"]]
    stop_rule = classify_stop_rule(sidecar_info, session_info, session_result)

    if not sidecar_info.get("found"):
        summary = f"failed: sidecar not found - {sidecar_info.get('error', '?')}"
    elif not session_info or not session_info.get("ok"):
        err = session_info.get("error") if session_info else "session creation not attempted"
        summary = f"failed: {err}" if err else "failed: session creation"
    elif session_result.get("ok") and denied:
        summary = f"completed with {len(denied)} permission(s) denied"
    elif session_result.get("ok"):
        summary = "success"
    elif session_result.get("error"):
        summary = f"failed: {session_result['error']}"
    elif denied:
        summary = f"interrupted: {len(denied)} permission(s) denied"

    lines = []
    lines.append("# Claude Code Execution Result")
    lines.append("")
    lines.append(f"- **Task**: C-14: cc-haha WS task runner MVP")
    lines.append(f"- **Date**: 2026-06-24")
    lines.append(f"- **Summary**: {summary}")
    lines.append("")
    lines.append("## Task")
    lines.append("")
    lines.append(f"```\n{task_text}\n```")
    lines.append("")
    lines.append("## Sidecar")
    lines.append("")
    lines.append(f"- **URL**: {sidecar_info.get('url', 'N/A')}")
    lines.append(f"- **source**: {sidecar_info.get('source', 'N/A')}")
    lines.append("")
    lines.append("## Session")
    lines.append("")
    session_id = session_result.get("session_id", "") or (session_info.get("session_id") if session_info else "")
    lines.append(f"- **sessionId**: {session_id or 'N/A'}")
    lines.append(f"- **elapsed**: {elapsed}s")
    ok = session_result.get("ok", False)
    lines.append(f"- **status**: {'OK' if ok else 'FAIL'}")
    if session_result.get("error"):
        lines.append(f"- **error**: {session_result['error']}")
    usage = session_result.get("usage", {})
    if usage:
        in_t = usage.get("input_tokens", "?")
        out_t = usage.get("output_tokens", "?")
        lines.append(f"- **tokens**: in={in_t}, out={out_t}")
    lines.append("")

    retained_output = _retain_safe_output(session_result.get("output_text", ""))
    if retained_output:
        lines.append("## Claude Output (retained)")
        lines.append("")
        lines.append("~~~~text")
        lines.append(retained_output)
        lines.append("~~~~")
        lines.append("")

    lines.append("## Stop Rule")
    lines.append("")
    lines.append(f"- **code**: {stop_rule['code']}")
    lines.append(f"- **stop**: {str(stop_rule['stop']).lower()}")
    lines.append(f"- **reason**: {stop_rule['reason']}")
    lines.append("")

    # \u6743\u9650\u8bf7\u6c42\u8bb0\u5f55
    if perms:
        lines.append("## \u6743\u9650\u8bf7\u6c42\u8bb0\u5f55")
        lines.append("")
        for p in perms:
            status = "\u2705 ALLOW" if p["allowed"] else "\u274c DENY"
            lines.append(f"| {status} | `{p['toolName']}` | {p.get('reason', '')} |")
        lines.append("")

    # event log
    events = session_result.get("events", [])
    think_n = session_result.get("thinking_count", 0)
    if events or think_n:
        lines.append("## Event Log")
        lines.append("")
        if think_n:
            lines.append(f"_(filtered {think_n} thinking events)_")
            lines.append("")
        lines.append("| # | type | detail |")
        lines.append("|---|------|--------|")
        for i, ev in enumerate(events):
            etype = ev.get("type", "?")
            info = ""
            if etype == "status":
                info = f"state={ev.get('state','')}"
            elif etype == "permission_request":
                # 从 permission_requests 查询实际决策（raw WS 事件不含 allowed 字段）
                req_id = ev.get("requestId", "")
                perm_result = "unknown"
                for p in session_result.get("permission_requests", []):
                    if p.get("requestId") == req_id:
                        perm_result = "ALLOW" if p.get("allowed") else "DENY"
                        break
                info = f"tool={ev.get('toolName','')} decision={perm_result}"
            elif etype == "message_complete":
                u = ev.get("usage", {})
                info = f"in={u.get('input_tokens','?')} out={u.get('output_tokens','?')}"
            elif etype == "error":
                info = f"code={ev.get('code','')}"
            elif etype == "tool_use_complete":
                info = f"tool={ev.get('toolName','')}"
            lines.append(f"| {i+1} | {etype} | {info} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_C-14 controlled WS delivery MVP, no auto-review/git/retry._")

    content = "\n".join(lines)
    result_file = (run_dir / "claude_result.md") if run_dir else (BRIDGE_DIR / "claude_result.md")
    write_text_atomic(result_file, content)
    _log(f"[FILE] claude_result.md written ({len(content)} chars)")
    return result_file


def update_state_json(
    task_name: str,
    run_id: str = "",
    session_id: str = "",
    session_reused: bool = False,
    stop_rule: dict | None = None,
    result_file: Path | None = None,
):
    """原子更新 state.json 为 NEED_CODEX_REVIEW。"""
    blocked_reason = (stop_rule or {}).get("reason", "") if (stop_rule or {}).get("stop") else ""
    with locked_state(STATE_FILE, default={}) as previous_state:
        completed_tasks = previous_state.get("supervised_completed_tasks")
        state = {
            "current_task": task_name,
            "stage": "NEED_CODEX_REVIEW",
            "owner": "codex",
            "last_actor": "claude_code",
            "run_id": run_id,
            "session_id": session_id,
            "session_reused": session_reused,
            "stop_rule": (stop_rule or {}).get("code", ""),
            "review_status": "",
            "retry_count": 0,
            "max_retry": 2,
            "updated_at": datetime.now().strftime("%Y-%m-%d"),
            "blocked_reason": blocked_reason,
        }
        if result_file is not None:
            state["claude_result_sha256"] = artifact_sha256(result_file)
            state["claude_result_file"] = result_file.name
        if isinstance(completed_tasks, list):
            state["supervised_completed_tasks"] = completed_tasks
        previous_state.clear()
        previous_state.update(state)
    _log(f"[FILE] state.json \u5df2\u66f4\u65b0\u4e3a NEED_CODEX_REVIEW")


def load_state_session_id(state_file: Path = STATE_FILE) -> str:
    """读取上一次记录的 cc-haha session_id；没有则返回空字符串。"""
    try:
        state = read_state(state_file)
    except BridgeStateError:
        return ""
    session_id = state.get("session_id", "")
    return session_id if isinstance(session_id, str) else ""


# ── \u4e3b\u6d41\u7a0b ──────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="C-14: cc-haha \u53d7\u63a7 WS \u4efb\u52a1\u6295\u9012 MVP")
    parser.add_argument("task", nargs="?", default="",
                        help="\u8981\u6295\u9012\u7684\u4efb\u52a1\u63cf\u8ff0\uff08\u53ef\u7528\u6807\u51c6\u8f93\u5165\u66ff\u4ee3\uff09")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"\u603b\u8d85\u65f6\u79d2\u6570\uff08\u9ed8\u8ba4 {DEFAULT_TIMEOUT}s\uff09")
    parser.add_argument("--task-file", type=str, default="",
                        help="\u4ece\u6587\u4ef6\u8bfb\u53d6\u4efb\u52a1\u63cf\u8ff0")
    parser.add_argument("--session-id", type=str, default="",
                        help="\u590d\u7528\u5df2\u6709 cc-haha sessionId\uff0c\u907f\u514d\u65b0\u5efa\u5bf9\u8bdd")
    parser.add_argument("--new-session", action="store_true",
                        help="\u5f3a\u5236\u65b0\u5efa cc-haha session\uff08\u4f1a\u5728\u4fa7\u8fb9\u680f\u51fa\u73b0\u65b0\u5bf9\u8bdd\uff09")

    args = parser.parse_args()

    # \u83b7\u53d6\u4efb\u52a1\u6587\u672c
    task_text = args.task
    if not task_text and args.task_file:
        task_text = Path(args.task_file).read_text(encoding="utf-8").strip()
    if not task_text and not sys.stdin.isatty():
        task_text = sys.stdin.read().strip()
    if not task_text:
        task_text = "\u751f\u6210\u4e00\u4e2a\u4e09\u76f8\u7535\u673a\u6b63\u53cd\u8f6c\u5e26\u6025\u505c\u548c\u8fc7\u8f7d\u4fdd\u62a4\u7684 SCL \u7a0b\u5e8f"
        _log(f"[INFO] \u672a\u6307\u5b9a\u4efb\u52a1\uff0c\u4f7f\u7528\u9ed8\u8ba4\u6d4b\u8bd5\u4efb\u52a1: {task_text[:60]}...")

    _log("=== C-14: cc-haha WS task runner MVP ===")
    start_ts = time.time()

    # ── Phase 0: ensure run directory ──
    task_name = "C-14: cc-haha WS task runner MVP"
    run_dir, run_id = ensure_run_dir(task_name)
    _log(f"[0/5] run_dir: {run_dir}")

    # Placeholders for partial results (always written at end)
    sidecar = {"found": False, "error": "not started", "source": None, "url": None, "host": None, "port": None}
    session = {"ok": False, "session_id": "", "error": None}
    ws_result = {
        "ok": False, "session_id": "", "events": [], "thinking_count": 0,
        "permission_requests": [], "output_text": [], "usage": {}, "error": None,
    }
    session_id = ""

    # ── Phase 1: discover sidecar ──
    _log("[1/5] discovering sidecar port...")
    try:
        sidecar = discover_sidecar()
        if not sidecar.get("found"):
            _log(f"[FAIL] sidecar unavailable: {sidecar.get('error', '?')}")
        else:
            base_url = sidecar["url"]
            _log(f"[OK] sidecar: {base_url} (source: {sidecar['source']})")

            # ── Phase 2: create session ──
            reuse_session_id = "" if args.new_session else (args.session_id.strip() or load_state_session_id())
            if reuse_session_id:
                _log(f"[2/5] reusing sessionId={reuse_session_id}")
            else:
                _log("[2/5] creating session POST /api/sessions...")
            session = resolve_session(base_url, reuse_session_id=reuse_session_id)
            if not session.get("ok"):
                _log(f"[FAIL] session creation failed: {session.get('error', '?')}")
            else:
                session_id = session["session_id"]
                if session.get("reused"):
                    _log(f"[OK] reused sessionId={session_id}")
                else:
                    _log(f"[OK] sessionId={session_id}")

                # ── Phase 3-4: WS + event loop ──
                ws_url = f"ws://{sidecar.get('host','127.0.0.1')}:{sidecar.get('port',0)}/ws/{session_id}"
                _log(f"[3/5] WS connect: {ws_url}")
                _log(f"[4/5] task delivery + event loop (timeout={args.timeout}s)")

                ws_result = run_ws_session(ws_url, task_text, timeout=args.timeout)
    except Exception as e:
        _log(f"[ERROR] unexpected: {e}")
        if not ws_result.get("error"):
            ws_result["error"] = str(e)
        traceback.print_exc()

    elapsed = round(time.time() - start_ts, 1)
    ws_ok = ws_result.get("ok", False)
    _log(f"[phase] session done, elapsed={elapsed}s, status={'OK' if ws_ok else 'FAIL'}")

    # ── Phase 5: always write bridge files (success or failure) ──
    _log("[5/5] writing bridge files...")
    result_file = write_claude_result(sidecar, ws_result, task_text, session, elapsed, run_dir=run_dir)
    stop_rule = classify_stop_rule(sidecar, session, ws_result)
    update_state_json(
        task_name,
        run_id,
        session_id=session_id,
        session_reused=bool(session.get("reused")),
        stop_rule=stop_rule,
        result_file=result_file,
    )

    # summary
    print()
    print("=" * 50)
    print(f"  C-14 execution complete")
    print(f"  status: {'[OK]' if ws_ok else '[FAIL]'}")
    print(f"  elapsed: {elapsed}s")
    print(f"  run_id: {run_id}")
    print(f"  session: {session_id}")
    if ws_result.get("usage"):
        u = ws_result["usage"]
        print(f"  token: in={u.get('input_tokens','?')} out={u.get('output_tokens','?')}")
    if ws_result.get("permission_requests"):
        denied_count = len([p for p in ws_result["permission_requests"] if not p["allowed"]])
        print(f"  permissions: {len(ws_result['permission_requests'])} ({denied_count} denied)")
    if ws_result.get("error"):
        print(f"  error: {ws_result['error']}")
    if not sidecar.get("found"):
        print(f"  error: {sidecar.get('error', 'sidecar not found')}")
    if not session.get("ok") and sidecar.get("found"):
        print(f"  error: session: {session.get('error', 'unknown')}")
    print(f"  result file: {run_dir / 'claude_result.md'}")
    print(f"  state: NEED_CODEX_REVIEW")
    print("=" * 50)

    sys.exit(0 if ws_ok else 1)


if __name__ == "__main__":
    main()
