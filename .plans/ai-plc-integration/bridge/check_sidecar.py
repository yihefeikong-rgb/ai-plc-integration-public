#!/usr/bin/env python3
"""
check_sidecar.py — cc-haha sidecar 端口发现 + 可用性探测 (C-13)

职责：
  1. 动态发现 cc-haha sidecar 端口（不假设固定端口）
  2. GET /health 探活
  3. 输出结构化诊断 JSON

只读约束：
  - 不创建/修改任何文件
  - 不写 sidecar 状态
  - 不调用 sidecar API 写操作
  - 不修改 Bridge 框架文件

返回码：
  0 — sidecar 可用（发现端口 + /health 可达）
  1 — sidecar 不可用（未发现端口 或 /health 异常）

用法：
  D:/Python3/python.exe check_sidecar.py
  CC_HAHA_PORT=3456 D:/Python3/python.exe check_sidecar.py   # 覆盖端口
"""

import json
import os
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ── 编码适配: Windows GBK 终端 ──────────────────────────
_ENC = sys.stdout.encoding or "utf-8"
_SUPPORTS_EMOJI = _ENC.lower() in ("utf-8", "utf8")


def _emoji(e: str) -> str:
    return e if _SUPPORTS_EMOJI else _ASCII_EMOJI.get(e, f"[{e}]")


_ASCII_EMOJI = {
    "\u2705": "[OK]",
    "\u26a0\ufe0f": "[WARN]",
    "\u274c": "[FAIL]",
    "\u2501": "-",
    "\u27a1": "->",
}

# ── 常量 ──────────────────────────────────────────────────

DEFAULT_STATE_FILE = Path.home() / ".claude" / "desktop-server-state.json"
SCAN_TIMEOUT = 1          # 每端口 TCP 连接超时（秒）
SEED_TIMEOUT = 0.5        # seed 端口探测超时（秒）
HEALTH_TIMEOUT = 3        # /health 请求超时（秒）
SCAN_MAX_PORTS = 40       # 扫描最大端口数
COMMON_PORTS = [3456, 3457, 3458, 3449, 3460, 8080, 3000, 5173]
SCAN_HOST = "127.0.0.1"

# ── 辅助 ──────────────────────────────────────────────────


def _make_result(
    found: bool,
    source: str | None = None,
    host: str | None = None,
    port: int | None = None,
    health_ok: bool | None = None,
    status_code: int | None = None,
    error: str | None = None,
    detail: dict | None = None,
) -> dict:
    """构造结构化诊断结果"""
    return {
        "found": found,
        "source": source,          # "state-file" | "scan" | "override" | None
        "host": host,
        "port": port,
        "health_ok": health_ok,
        "status_code": status_code,
        "error": error,
        "detail": detail or {},
    }


def _gather_seed_ports(layer1_port: int | None) -> list[int]:
    """
    收集扫描种子端口：
    - Layer 1 的 lastPort（即使 /health 失败也加入）
    - ±10 范围扩散
    - 常见端口
    去重后返回
    """
    seeds: set[int] = set()
    seeds.update(COMMON_PORTS)

    # lastPort ± 10 范围扩散
    if layer1_port is not None:
        seeds.add(layer1_port)
        for offset in range(1, 11):
            if layer1_port + offset <= 65535:
                seeds.add(layer1_port + offset)
            if layer1_port - offset >= 1:
                seeds.add(layer1_port - offset)

    return sorted(seeds)


# ── 探测层: TCP + /health ───────────────────────────────


def _try_tcp_port(host: str, port: int, timeout: int = SCAN_TIMEOUT) -> bool:
    """尝试 TCP 连接指定端口"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _check_health(host: str, port: int, timeout: int = HEALTH_TIMEOUT) -> dict:
    """GET /health 探活"""
    url = f"http://{host}:{port}/health"
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
            try:
                body_json = json.loads(body)
                health_ok = status == 200 and isinstance(body_json, dict)
            except json.JSONDecodeError:
                body_json = None
                health_ok = False
            return {
                "health_ok": health_ok,
                "status_code": status,
                "body_preview": body[:300] if body else "",
                "error": None,
            }
    except HTTPError as e:
        return {"health_ok": False, "status_code": e.code, "body_preview": "", "error": f"HTTP {e.code}"}
    except URLError as e:
        return {"health_ok": False, "status_code": None, "body_preview": "", "error": f"连接失败: {e.reason}"}
    except OSError as e:
        return {"health_ok": False, "status_code": None, "body_preview": "", "error": f"网络错误: {e}"}


# ── 端口发现: 三层优先级 ─────────────────────────────────


def layer1_state_file(state_file: Path = DEFAULT_STATE_FILE) -> dict:
    """
    Layer 1: 读取 ~/.claude/desktop-server-state.json 的 lastPort

    sidecar 每次启动后由 ElectronServerRuntime.writeLastServerPort()
    将本次端口号写入此文件，供下次启动时复用（跨重启粘性）。
    """
    if not state_file.exists():
        return _make_result(found=False, source="state-file", error=f"文件不存在: {state_file}")

    try:
        raw = state_file.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError) as e:
        return _make_result(found=False, source="state-file", error=f"读取失败: {e}")

    port = data.get("lastPort")
    if port is None:
        return _make_result(
            found=False, source="state-file",
            error="无 lastPort 字段",
            detail={"keys": list(data.keys()), "file": str(state_file)},
        )
    if not isinstance(port, int) or port < 1 or port > 65535:
        return _make_result(found=False, source="state-file", error=f"lastPort 值无效: {port}")

    return _make_result(found=True, source="state-file", host=SCAN_HOST, port=port,
                        detail={"file": str(state_file)})


def layer2_scan(seed_ports: list[int] | None = None) -> dict:
    """
    Layer 2: localhost 端口扫描

    策略：
      1. seed 端口 = lastPort ± 10 + 常见端口
      2. 先用短超时 0.5s 快速探测
      3. 快速探测失败后全量扫描
      4. 对开放端口做 /health 验证
    """
    if not seed_ports:
        seed_ports = COMMON_PORTS

    candidates = sorted(set(seed_ports))[:SCAN_MAX_PORTS]

    # Phase 1: 快速探测前 10 个候选端口
    fast_candidates = candidates[:10]
    for port in fast_candidates:
        if _try_tcp_port(SCAN_HOST, port, timeout=SEED_TIMEOUT):
            health = _check_health(SCAN_HOST, port)
            if health["health_ok"]:
                return _make_result(found=True, source="scan", host=SCAN_HOST, port=port,
                                    health_ok=True, status_code=200,
                                    detail={"method": "fast", "health": health})

    # Phase 2: 全量扫描剩余
    open_ports: list[int] = []
    for port in candidates:
        if port in fast_candidates:
            continue
        if _try_tcp_port(SCAN_HOST, port, timeout=SCAN_TIMEOUT):
            open_ports.append(port)

    if not open_ports:
        return _make_result(found=False, source="scan",
                            error=f"扫描 {len(candidates)} 端口，0 开放",
                            detail={"scanned_count": len(candidates)})

    for port in open_ports:
        health = _check_health(SCAN_HOST, port)
        if health["health_ok"]:
            return _make_result(found=True, source="scan", host=SCAN_HOST, port=port,
                                health_ok=True, status_code=200,
                                detail={"method": "full", "open_ports": open_ports, "health": health})

    return _make_result(found=False, source="scan",
                        error=f"{len(open_ports)} 端口开放但无 /health 响应",
                        detail={"open_ports": open_ports, "host": SCAN_HOST})


def layer3_override() -> dict:
    """
    Layer 3: 环境变量覆盖（兜底，仅在 Layer 1 和 2 都失败时生效）

    优先级（从高到低）：
      1. CC_HAHA_PORT=3456
      2. CC_HAHA_HOST=127.0.0.1 + CC_HAHA_PORT=3456
      3. CC_HAHA_URL=http://127.0.0.1:3456
    """
    host = os.environ.get("CC_HAHA_HOST", SCAN_HOST)
    port_str = os.environ.get("CC_HAHA_PORT", "")

    if not port_str:
        url = os.environ.get("CC_HAHA_URL", "")
        if url:
            try:
                parsed = urlparse(url)
                host = parsed.hostname or SCAN_HOST
                port_str = str(parsed.port) if parsed.port else ""
            except Exception:
                pass

    if not port_str:
        return _make_result(found=False, source="override", error="未设置 CC_HAHA_PORT 或 CC_HAHA_URL")

    try:
        port = int(port_str)
    except ValueError:
        return _make_result(found=False, source="override", error=f"端口值无效: {port_str}")

    return _make_result(found=True, source="override", host=host, port=port,
                        detail={"CC_HAHA_HOST": host, "CC_HAHA_PORT": port})


# ── 主流程 ──────────────────────────────────────────────


def main():
    start_ts = time.time()

    output = {
        "tool": "check_sidecar.py",
        "version": "1.0.0",
        "constraints": ["只读操作，不修改任何文件", "不假设固定端口"],
        "layers": [],
    }

    final_port: int | None = None
    final_host: str | None = None
    final_source: str | None = None

    # ── Layer 1: state file ──
    # 找到后立即验证 /health。只有 /health 成功才锁定最终结论。
    # 如果端口不通，把端口传入 Layer 2 做 seed 扫描（stale lastPort 场景）。
    r1 = layer1_state_file()
    output["layers"].append({"layer": 1, "name": "state-file", **r1})
    if r1["found"]:
        health = _check_health(r1["host"], r1["port"])
        if health["health_ok"]:
            final_port = r1["port"]
            final_host = r1["host"]
            final_source = "state-file"
            output["layers"][-1]["health_on_discovery"] = health
        else:
            # Layer 1 端口不通 — stale lastPort 场景，不放 final_port
            pass

    # -- Layer 2: scan (short-circuit: 仅在 Layer 1 失败时运行) --
    if not final_port:
        seed = _gather_seed_ports(r1["port"] if r1["found"] else None)
        r2 = layer2_scan(seed_ports=seed)
        output["layers"].append({"layer": 2, "name": "scan", **r2})
        if r2["found"]:
            final_port = r2["port"]
            final_host = r2["host"]
            final_source = "scan"
    else:
        output["layers"].append({
            "layer": 2, "name": "scan", "found": False,
            "skipped": True, "reason": "Layer 1 已发现健康端口"
        })

    # -- Layer 3: override --
    if not final_port:
        r3 = layer3_override()
        output["layers"].append({"layer": 3, "name": "override", **r3})
        if r3["found"]:
            final_port = r3["port"]
            final_host = r3["host"]
            final_source = "override"
    else:
        output["layers"].append({
            "layer": 3, "name": "override", "found": False,
            "skipped": True, "reason": "前序层已发现健康端口"
        })

    # ── 最终结论 ──
    elapsed = round(time.time() - start_ts, 2)

    if final_port and final_host:
        health = _check_health(final_host, final_port)
        output["conclusion"] = {
            "found": True,
            "source": final_source,
            "host": final_host,
            "port": final_port,
            "url": f"http://{final_host}:{final_port}",
            "health_ok": health["health_ok"],
            "status_code": health["status_code"],
            "error": health["error"],
            "elapsed_seconds": elapsed,
        }
    else:
        output["conclusion"] = {
            "found": False,
            "source": None,
            "host": None,
            "port": None,
            "url": None,
            "health_ok": None,
            "status_code": None,
            "error": (
                "三层发现均未找到 sidecar：\n"
                "  Layer 1 (state-file): 文件不存在或无效\n"
                "  Layer 2 (scan): 无 /health 响应\n"
                "  Layer 3 (override): 未配置环境变量"
            ),
            "elapsed_seconds": elapsed,
        }

    # ── 输出 ──
    c = output["conclusion"]

    json_str = json.dumps(output, indent=2, ensure_ascii=False)
    try:
        print(json_str)
    except UnicodeEncodeError:
        print(json_str.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))

    sep = _emoji("\u2501") * 48
    print()
    print(sep)
    print(f"  C-13: cc-haha sidecar {_emoji('\u2705')} 可用性探测")
    print(f"  {_emoji('\u2705')} 耗时: {elapsed}s")
    print(sep)

    if c["found"] and c["health_ok"]:
        print(f"  {_emoji('\u2705')} sidecar 可用")
        print(f"     URL:    {c['url']}")
        print(f"     {_emoji('\u2705')} 端口来源: {c['source']}")
    elif c["found"] and not c["health_ok"]:
        print(f"  {_emoji('\u26a0\ufe0f')} 端口 {c['port']} 可达但 /health 异常")
        print(f"     {_emoji('\u2705')} 状态码: {c['status_code']}")
        print(f"     {_emoji('\u2705')} 错误:   {c['error']}")
        print(f"     {_emoji('\u2705')} 端口来源: {c['source']}")
    else:
        print(f"  {_emoji('\u274c')} sidecar 不可用")
        print(f"     {c['error']}")
        print()
        print(f"  {_emoji('\u27a1')} 请确认 cc-haha 桌面端已启动")
        print(f"  {_emoji('\u27a1')} 或用 CC_HAHA_PORT 环境变量指定端口:")
        print(f"      CC_HAHA_PORT=3456 {sys.executable} {__file__}")

    print(sep)

    sys.exit(0 if c["found"] and c["health_ok"] else 1)


if __name__ == "__main__":
    main()
