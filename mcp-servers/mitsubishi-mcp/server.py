"""
三菱 MC 协议 MCP Server — 阶段1：读 + 阶段2：写
支持 FX3U / FX5U，TCP Binary 模式
"""

import os
import re
import sys
import hmac
import asyncio
import struct
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_MODULE_DIR = Path(__file__).parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))
if str(_MODULE_DIR) not in sys.path:
    sys.path.append(str(_MODULE_DIR))

from fastmcp import FastMCP
from mcp_common.config import env_config
from safety.validator import validator as safety_validator
from safety.shadow_simulator import shadow_sim
from safety.confirmation import ConfirmationError, ConfirmationService
from mcp_common.audit import (
    authenticated_actor, get_audit_logger,
    AuditConfigurationError, AuditStorageError,
)

audit = get_audit_logger()
from mc_protocol import (
    build_read_request, build_write_request,
    parse_read_response, parse_write_response, MCFrameError,
    RESP_HEADER_LEN, is_bit_device,
)

settings = env_config()

mcp = FastMCP("mitsubishi-plc")
_reader: asyncio.StreamReader | None = None
_writer: asyncio.StreamWriter | None = None

# 连接与 I/O 超时（秒）
CONNECT_TIMEOUT = 5.0
IO_TIMEOUT = 5.0
_MAX_BATCH_ADDRESSES = 256

# 响应 DataLen 合理上限：本服务单次批量最多 _MAX_BATCH_ADDRESSES 个点，任何
# 合法响应的 DataLen ≤ 2 + _MAX_BATCH_ADDRESSES*2 = 514 字节。取 0x8000 作
# 防御性上限：DataLen bit15 置位（≥ 0x8000）绝不可能是本服务所发请求的合法
# 响应，直接判定为异常帧拒绝，避免按该长度持锁等待。
_MAX_RESPONSE_DATA_LEN = 0x8000

# 响应帧总读取时限：正常响应由 PLC 立即返回（毫秒级）。该时限拦截恶意/异常
# peer 声明超大 DataLen 后缓慢滴灌、在持全局 _io_lock 期间长时间独占互斥锁的
# 拒绝服务行为（锁被独占时全部并发读写被卡住）。fail-closed：超时即抛错。
_FRAME_READ_TIMEOUT = IO_TIMEOUT * 2

# 全局共享 TCP 流上任何请求-响应交换都必须互斥，否则并发请求的帧会在
# 同一流上交错错配（读到别的请求的响应）。_conn_lock 串行化建连，
# _io_lock 串行化每个请求的完整写-读交换。
_conn_lock = asyncio.Lock()
_io_lock = asyncio.Lock()

# 三菱控制型设备：safety.validator 的 FORBIDDEN/CONFIRM_PATTERNS 与互锁规则
# 全部是 S7 标签名模式（DB1.*、ESTOP/MOTOR…），对三菱地址（Y20/M100/L0…）永不
# 匹配。以下地址类型必须 fail-closed：强制人工确认，禁止静默直写。
_MELSEC_CONFIRM_PREFIXES = frozenset({"Y", "L", "S", "B", "F"})
_MELSEC_SPECIAL_RELAY_THRESHOLD = 8000  # FX3U 特殊继电器 M8xxx / 特殊数据寄存器 D8xxx

# ── 认证 ──
_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")
confirmation_service = ConfirmationService()


def _require_auth(token: str):
    """验证 auth token（必须设置 MCP_AUTH_TOKEN），常数时间比较防时序侧信道

    isinstance 只挡住非字符串；非 ASCII str 会让 hmac.compare_digest 抛
    TypeError（未捕获将导致进程崩溃），统一转 UTF-8 字节再比较。
    """
    if not _AUTH_TOKEN:
        raise PermissionError("MCP_AUTH_TOKEN 未配置，服务不可用")
    if not isinstance(token, str) or not hmac.compare_digest(
        token.encode("utf-8"), _AUTH_TOKEN.encode("utf-8")
    ):
        raise PermissionError("认证失败：无效的 auth token")


async def _close_connection():
    """关闭并清除全局 TCP 连接（加锁避免与建连竞态）。"""
    global _reader, _writer
    async with _conn_lock:
        writer = _writer
        _reader, _writer = None, None
    if writer is not None:
        try:
            writer.close()
        except Exception:
            pass
        try:
            await asyncio.wait_for(writer.wait_closed(), timeout=IO_TIMEOUT)
        except Exception:
            pass


async def get_connection():
    """获取与 PLC 的 TCP 连接。

    - 用 _conn_lock 串行化建连，杜绝并发首连竞态泄漏 socket；
    - 建连带超时（CONNECT_TIMEOUT），避免连接挂起时永久阻塞；
    - 每次调用检查连接健康（EOF/关闭），失效立即重建（断线自动重连）。
    """
    global _reader, _writer
    async with _conn_lock:
        if (_reader is not None and _writer is not None
                and not _reader.at_eof()
                and not _writer.is_closing()):
            return _reader, _writer
        # 连接缺失或已失效：丢弃旧流后重建
        old_writer = _writer
        _reader, _writer = None, None
        if old_writer is not None:
            try:
                old_writer.close()
            except Exception:
                pass
        _reader, _writer = await asyncio.wait_for(
            asyncio.open_connection(settings.melsec_host, settings.melsec_port),
            timeout=CONNECT_TIMEOUT,
        )
        return _reader, _writer


async def _read_exact(reader: asyncio.StreamReader, n: int) -> bytes:
    """读取恰好 n 字节；TCP 分包时循环累积，EOF 抛 IncompleteReadError。"""
    chunks = b""
    while len(chunks) < n:
        chunk = await asyncio.wait_for(reader.read(n - len(chunks)), timeout=IO_TIMEOUT)
        if not chunk:
            raise asyncio.IncompleteReadError(chunks, n)
        chunks += chunk
    return chunks[:n]


async def _read_frame(reader: asyncio.StreamReader) -> bytes:
    """按响应帧头 DataLen 精确读取一帧，处理 TCP 分包/粘包。

    响应头 9 字节（Subheader~DataLen），DataLen 位于 offset 7:9，
    帧总长 = 9 + DataLen（DataLen 含 EndCode(2) + Data）。
    整个帧读取受 _FRAME_READ_TIMEOUT 总时限约束，防止恶意 peer 声明超大
    DataLen 后缓慢滴灌、持 _io_lock 无限期等待。
    """
    async def _read_frame_once() -> bytes:
        header = await _read_exact(reader, RESP_HEADER_LEN)
        data_len = struct.unpack("<H", header[7:9])[0]
        if not (2 <= data_len <= _MAX_RESPONSE_DATA_LEN):
            raise MCFrameError(f"响应 DataLen 无效: {data_len}")
        body = await _read_exact(reader, data_len)
        return header + body
    return await asyncio.wait_for(_read_frame_once(), timeout=_FRAME_READ_TIMEOUT)


async def _send_frame(frame: bytes, *, retry_on_io_error: bool) -> bytes:
    """在共享连接上发送请求帧并读取完整响应帧。

    整个交换在 _io_lock 内互斥，杜绝并发请求帧交错错配；
    IO 故障时重建连接并按需重试一次（仅读侧重试，写侧不自动重试以免重复写入）。
    """
    last_exc = None
    attempts = 2 if retry_on_io_error else 1
    for _ in range(attempts):
        try:
            async with _io_lock:
                r, w = await get_connection()
                w.write(frame)
                await w.drain()
                return await _read_frame(r)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError,
                OSError, ConnectionError, MCFrameError) as exc:
            last_exc = exc
            await _close_connection()
    raise last_exc


async def _read_points(start_addr: str, count: int) -> list[int]:
    """读取连续 count 个点；IO 故障重建连接后重试一次。"""
    frame = build_read_request(start_addr, count)
    try:
        resp = await _send_frame(frame, retry_on_io_error=True)
        return parse_read_response(resp, start_addr)
    except (MCFrameError, struct.error):
        # 帧不完整或 PLC 返回错误码：连接流可能错位，关闭重建
        await _close_connection()
        raise


def _confirmation_device_id() -> str:
    return f"melsec:{settings.melsec_host}:{settings.melsec_port}"


# ── 审计（同步阻塞 I/O 放到线程池，避免阻塞 asyncio 事件循环） ──

def _safe_detail(exc: Exception) -> str:
    """审计用的异常摘要（协议/端点细节不回传给客户端）。"""
    return f"{type(exc).__name__}: {str(exc)[:200]}"


async def _audit_log(action, target, value="", operator="ai-agent", success=True, detail=""):
    """审计日志尽力而为：审计存储/配置失败不得改变业务结果或穿透到客户端。

    返回 True=已落盘，False=审计写入失败；写成功路径据此 fail-closed 熔断。
    控制闸门（_audit_control_intent / _audit_confirmed）仍保持严格失败语义，
    其异常在调用处显式处理（fail-closed 阻断写入）。
    """
    try:
        await asyncio.to_thread(
            audit.log, action, target, value,
            operator=operator, success=success, detail=detail,
        )
        return True
    except Exception as exc:
        print(f"[mitsubishi-mcp] 审计记录失败（不影响操作结果）: {type(exc).__name__}",
              file=sys.stderr)
        return False


async def _audit_control_intent(operation, target, actor, params):
    """控制意图审计（写盘前置条件，失败即阻断控制动作）。"""
    await asyncio.to_thread(audit.begin_control_operation, operation, target, actor, params)


async def _audit_confirmed(addr, value, actor, payload):
    """记录人工确认闭环：approver 身份与 audit_id 落入审计链。"""
    await asyncio.to_thread(
        audit.log_operation,
        "write_confirmed",
        target=addr,
        operator=actor,
        approver=payload.get("approver", ""),
        audit_id=payload.get("audit_id", ""),
        value=str(value),
        success=True,
    )


# ── 三菱本地写防护（S7 规则无法覆盖的 fail-closed 兜底） ──

def _melsec_device_prefix(addr: str) -> str:
    m = re.match(r"^([A-Z]+)(\d+)$", addr.upper())
    return m.group(1) if m else ""


def _melsec_write_guard(addr: str, value: int) -> tuple[bool, str]:
    """拒绝只读输入 X 与非法数值。返回 (允许, 拒绝原因)。"""
    prefix = _melsec_device_prefix(addr)
    if not prefix:
        return False, f"无效的三菱地址: {addr}"
    if prefix == "X":
        return False, f"禁止写入输入端子: {addr}（X 为只读输入）"
    if is_bit_device(addr):
        if not isinstance(value, int) or value not in (0, 1):
            return False, f"位设备 {addr} 只接受 0/1，收到 {value!r}"
    else:
        if not isinstance(value, int):
            return False, f"字设备 {addr} 需要整数，收到 {type(value).__name__}"
        # 与 mc_protocol.build_write_request 的 16 位补码编码契约一致：
        # -32768~-1 按补码编码为 0x8000~0xFFFF，0~65535 原值编码
        # （test_build_write_negative 已固化 -1 -> 0xFFFF 路径）。
        if not (-0x8000 <= value <= 0xFFFF):
            return False, f"字设备 {addr} 值超出 -32768~65535 范围: {value}"
    return True, ""


def _melsec_control_address(addr: str) -> bool:
    """三菱控制型地址需人工确认（S7 互锁规则无法覆盖，fail-closed）。"""
    prefix = _melsec_device_prefix(addr)
    if prefix in _MELSEC_CONFIRM_PREFIXES:
        return True
    m = re.match(r"^([A-Z]+)(\d+)$", addr.upper())
    if m and prefix in ("M", "D"):
        return int(m.group(2)) >= _MELSEC_SPECIAL_RELAY_THRESHOLD
    return False


def _register_write_error() -> None:
    """在 validator 锁内登记写入异常，避免被并发成功校验清零。"""
    with safety_validator._lock:
        safety_validator.consecutive_errors += 1


# ===== 阶段1：读取 =====

@mcp.tool()
async def read_device(addr: str, auth_token: str = "") -> dict:
    """读取单个设备地址（如 'M100', 'D200'）"""
    _require_auth(auth_token)
    try:
        values = await _read_points(addr, 1)
    except MCFrameError as e:
        await _audit_log("read", addr, success=False, detail=_safe_detail(e))
        return {"device": addr, "status": "error", "error": str(e)}
    except (asyncio.TimeoutError, asyncio.IncompleteReadError,
            OSError, ConnectionError, struct.error) as e:
        await _audit_log("read", addr, success=False, detail=_safe_detail(e))
        return {"device": addr, "status": "error", "error": "读取失败，请稍后重试"}
    if not values:
        await _audit_log("read", addr, success=False, detail="PLC 返回空响应")
        return {"device": addr, "status": "error", "error": "PLC 返回空响应"}
    await _audit_log("read", addr, str(values[0]), success=True)
    return {"device": addr, "value": values[0], "status": "ok"}


def _group_contiguous(addresses: list[str]) -> list[tuple[str, int, list[str]]]:
    """把地址按设备类型 + 连续偏移合并为批，返回 (前缀, 起始偏移, 成员地址)。"""
    by_prefix: dict[str, list[tuple[int, str]]] = {}
    for a in addresses:
        m = re.match(r"^([A-Z]+)(\d+)$", a.upper())
        if not m:
            continue
        by_prefix.setdefault(m.group(1), []).append((int(m.group(2)), a))
    groups: list[tuple[str, int, list[str]]] = []
    for prefix, items in by_prefix.items():
        items.sort()
        run_start = items[0][0]
        run_members: list[str] = []
        prev = None
        for off, a in items:
            if prev is not None and off != prev + 1:
                groups.append((prefix, run_start, run_members))
                run_start = off
                run_members = []
            run_members.append(a)
            prev = off
        if run_members:
            groups.append((prefix, run_start, run_members))
    return groups


@mcp.tool()
async def read_devices(addresses: list[str], auth_token: str = "") -> list[dict]:
    """批量读取设备（连续地址合并为一帧读取，减少往返）"""
    _require_auth(auth_token)
    if len(addresses) > _MAX_BATCH_ADDRESSES:
        raise ValueError(f"单次批量读取最多 {_MAX_BATCH_ADDRESSES} 个地址")
    results: dict[str, dict] = {}
    for prefix, start, members in _group_contiguous(addresses):
        start_addr = f"{prefix}{start}"
        count = len(members)
        try:
            values = await _read_points(start_addr, count)
        except MCFrameError as e:
            await _audit_log("read", start_addr, success=False, detail=_safe_detail(e))
            for a in members:
                results[a] = {"device": a, "status": "error", "error": str(e)}
            continue
        except (asyncio.TimeoutError, asyncio.IncompleteReadError,
                OSError, ConnectionError, struct.error) as e:
            await _audit_log("read", start_addr, success=False, detail=_safe_detail(e))
            for a in members:
                results[a] = {"device": a, "status": "error", "error": "读取失败，请稍后重试"}
            continue
        if len(values) < count:
            await _audit_log("read", start_addr, success=False, detail="批量读取返回点数不足")
            for a in members:
                results[a] = {"device": a, "status": "error", "error": "PLC 返回数据不完整"}
            continue
        for i, a in enumerate(members):
            results[a] = {"device": a, "value": values[i], "status": "ok"}
        await _audit_log("read_batch", start_addr, str(count), success=True)
    return [results.get(a, {"device": a, "status": "error", "error": "地址无效或设备类型不支持"})
            for a in addresses]


# ===== 阶段2：写入（带安全校验）=====

@mcp.tool()
async def write_device(
    addr: str,
    value: int,
    operator: str = "ai-agent",
    auth_token: str = "",
    confirmation_token: str = "",
) -> dict:
    """写入设备地址（带安全校验）"""
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "melsec")

    # 1. 本地写防护：拒绝 X 只读输入与非法数值（不依赖 PLC 连接）
    allowed, guard_reason = _melsec_write_guard(addr, value)
    if not allowed:
        await _audit_log("write_blocked", addr, str(value), operator=actor,
                         success=False, detail=guard_reason)
        return {"device": addr, "status": "blocked", "reason": guard_reason}

    # 2. S7 规则校验 + 熔断（对三菱地址规则覆盖有限，仅作兜底）
    result = safety_validator.validate(addr, value)
    if not result.allowed:
        await _audit_log("write_blocked", addr, str(value), operator=actor,
                         success=False, detail=result.reason)
        return {"device": addr, "status": "blocked", "reason": result.reason}

    # 3. 人工确认：S7 规则命中，或三菱控制型地址（Y/L/S/B/F、M/D 特殊寄存器）
    needs_confirmation = result.needs_confirmation or _melsec_control_address(addr)
    if needs_confirmation:
        if not confirmation_token:
            reason = f"需要人工确认: {addr}"
            await _audit_log("write_blocked", addr, str(value), operator=actor,
                             success=False, detail=reason)
            return {"device": addr, "status": "blocked", "reason": reason}
        try:
            payload = await asyncio.to_thread(
                confirmation_service.consume,
                confirmation_token,
                operator=actor,
                target=addr,
                value=value,
                device_id=_confirmation_device_id(),
            )
        except ConfirmationError as exc:
            reason = str(exc)
            await _audit_log("write_blocked", addr, str(value), operator=actor,
                             success=False, detail=reason)
            return {"device": addr, "status": "blocked", "reason": reason}
        # 审计闭环：approver 身份与 audit_id 必须落入审计链（确认令牌绑定审计）
        try:
            await _audit_confirmed(addr, value, actor, payload)
        except (AuditStorageError, AuditConfigurationError) as exc:
            # 确认闭环无法落审计链 → fail-closed 阻断写入（已消费的确认令牌
            # 不可复用），干净错误返回，不向客户端泄漏内部审计路径
            _register_write_error()
            await _audit_log("write_blocked", addr, str(value), operator=actor,
                             success=False, detail=_safe_detail(exc))
            return {"device": addr, "status": "error",
                    "error": "审计链不可用，确认闭环未记录，写入已阻断"}

    # 4. 影子前置检查（静态规则；simulate_write 未使用 PLC 当前值做变化率检测，
    #    属已知限制，见 notes 跨文件项；对三菱地址的主要护栏是第 1/3 步）
    sim_result = await shadow_sim.simulate_write(addr, value)
    if not sim_result.safe:
        await _audit_log("shadow_rejected", addr, str(value), operator=actor,
                         success=False, detail=sim_result.reason)
        return {"device": addr, "status": "blocked", "reason": sim_result.reason}

    # 5. 写入（写失败不自动重试，避免重复写入；连接失效时重建）
    try:
        await _audit_control_intent(
            "melsec.write_device", addr, actor,
            {"address": addr, "value": value},
        )
        frame = build_write_request(addr, value)
        resp = await _send_frame(frame, retry_on_io_error=False)
        parse_write_response(resp)
    except (AuditStorageError, AuditConfigurationError) as exc:
        # 控制意图审计闸门失败 → fail-closed 阻断控制动作（绝不写 PLC），
        # 干净错误返回并计入熔断，不向客户端泄漏内部审计路径
        _register_write_error()
        await _audit_log("write", addr, str(value), operator=actor,
                         success=False, detail=_safe_detail(exc))
        return {"device": addr, "status": "error",
                "error": "审计链不可用，写入已阻断（需人工介入）"}
    except MCFrameError as e:
        _register_write_error()
        await _audit_log("write", addr, str(value), operator=actor,
                         success=False, detail=_safe_detail(e))
        return {"device": addr, "status": "error", "error": str(e)}
    except (asyncio.TimeoutError, asyncio.IncompleteReadError,
            OSError, ConnectionError, struct.error) as e:
        _register_write_error()
        await _audit_log("write", addr, str(value), operator=actor,
                         success=False, detail=_safe_detail(e))
        return {"device": addr, "status": "error", "error": "写入失败，请稍后重试"}

    # 写入已执行但审计闭环失败 → fail-closed：如实报错并计入熔断，
    # 提示需人工介入（与 modbus-mcp 契约一致，不伪装成功）
    if not await _audit_log("write", addr, str(value), operator=actor, success=True):
        _register_write_error()
        return {"device": addr, "value": value, "status": "error",
                "error": "写入已执行但审计记录失败（已计入熔断，需人工介入）"}
    return {"device": addr, "value": value, "status": "ok",
            "needs_confirmation": needs_confirmation}


if __name__ == "__main__":
    mcp.run()
