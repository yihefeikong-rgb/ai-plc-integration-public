"""
Modbus TCP MCP Server — OpenPLC 仿真 / 通用 Modbus 设备
阶段1：读线圈/寄存器  阶段2：写线圈/寄存器（带安全校验）
"""

import asyncio
import hmac
import json
import os
import sys
import threading
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))

from fastmcp import FastMCP
from pymodbus.client import ModbusTcpClient
from mcp_common.config import env_config
from safety.validator import validator as safety_validator
from safety.shadow_simulator import shadow_sim
from safety.confirmation import ConfirmationError, ConfirmationService
from mcp_common.audit import authenticated_actor, get_audit_logger

audit = get_audit_logger()

settings = env_config()

mcp = FastMCP("modbus-plc")

# ── Modbus 协议参数（限制单次调用阻塞时长） ──
_MODBUS_TIMEOUT = 3.0
_MODBUS_RETRIES = 0                 # 默认 3 次重试 → 无响应时阻塞 3s×4；降为单次尝试
_MODBUS_MAX_ADDRESS = 0xFFFF        # Modbus 线圈/寄存器地址空间 0..65535
_MODBUS_MAX_READ_REGISTERS = 125    # Modbus 协议单帧最大读保持寄存器数
_MODBUS_MAX_READ_BITS = 2000        # Modbus 协议单帧最大读线圈/离散输入数

_READ_ERROR = "Modbus 读取失败（详细原因已记录审计日志）"
_WRITE_ERROR = "Modbus 写入失败（详细原因已记录审计日志）"

_client: ModbusTcpClient | None = None
_client_lock = threading.Lock()

# ── 认证 ──
_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")
confirmation_service = ConfirmationService()


def _require_auth(token: str):
    """验证 auth token（必须设置 MCP_AUTH_TOKEN）

    使用恒定时间比较，且不向未认证调用者泄露服务器认证配置状态。
    isinstance 前置检查 + UTF-8 字节比较：非字符串直接拒绝，非 ASCII str
    也不会让 hmac.compare_digest 抛 TypeError（与 desktop-mcp 一致）。
    """
    if (
        not _AUTH_TOKEN
        or not isinstance(token, str)
        or not hmac.compare_digest(token.encode("utf-8"), _AUTH_TOKEN.encode("utf-8"))
    ):
        raise PermissionError("认证失败：无效的 auth token")


# ── Modbus 地址 → 语义名称映射（让安全规则可命中） ──
# 映射来源：env MODBUS_TAG_NAMES(JSON) 优先，其次 edge-gateway/config/tags.json。
# 未配置映射的地址在写入时 fail-closed（强制人工确认）。
_TAG_NAME_FILE = _PROJECT_ROOT / "edge-gateway" / "config" / "tags.json"


def _load_tag_names() -> dict[str, str]:
    mapping: dict[str, str] = {}
    try:
        raw = os.environ.get("MODBUS_TAG_NAMES", "")
        if raw:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                mapping.update({str(k): str(v) for k, v in parsed.items() if v})
    except (ValueError, TypeError):
        pass
    try:
        parsed = json.loads(_TAG_NAME_FILE.read_text(encoding="utf-8"))
        if isinstance(parsed, list):
            mapping.update(
                {
                    str(item["tag"]): str(item["name"])
                    for item in parsed
                    if isinstance(item, dict) and item.get("tag") and item.get("name")
                }
            )
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return mapping


_SAFETY_TAG_NAMES = _load_tag_names()


def _safety_tag_name(kind: str, address: int) -> str | None:
    """返回地址对应的语义名称；未配置映射时返回 None（fail-closed）。"""
    return _SAFETY_TAG_NAMES.get(f"{kind}.{address}")


# ── Modbus 协议级入参校验（写前校验，越界值在消费人工确认令牌前就被拒绝） ──

def _validate_read_params(kind: str, address: int, count: int, max_count: int) -> str | None:
    if not isinstance(address, int) or isinstance(address, bool) \
            or not 0 <= address <= _MODBUS_MAX_ADDRESS:
        return f"{kind} 地址必须在 0..{_MODBUS_MAX_ADDRESS} 范围内"
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= max_count:
        return f"{kind} 读取数量必须在 1..{max_count} 范围内"
    if address + count - 1 > _MODBUS_MAX_ADDRESS:
        return f"{kind} 读取范围超出地址空间: 起始 {address} 读取 {count} 个将越过 0xFFFF"
    return None


def _validate_write_params(kind: str, address: int, value) -> str | None:
    if not isinstance(address, int) or isinstance(address, bool) \
            or not 0 <= address <= _MODBUS_MAX_ADDRESS:
        return f"{kind} 地址必须在 0..{_MODBUS_MAX_ADDRESS} 范围内"
    if kind == "coil":
        if isinstance(value, bool):
            return None
        if isinstance(value, int) and value in (0, 1):
            return None
        return "线圈值必须是布尔类型（True/False 或 0/1）"
    # register
    if isinstance(value, bool) or not isinstance(value, int):
        return "寄存器值必须是整数"
    if not 0 <= value <= 0xFFFF:
        return "寄存器值必须在 0..65535 范围内（16 位无符号）"
    return None


# ── 熔断计数 ──
# 注意：safety_validator.consecutive_errors 会在下一次 validate() 通过全部检查时被清零
# （safety/validator.py `self.consecutive_errors = 0`），因此设备/网络写失败永远无法
# 通过它累计到阈值。这里在 server 侧维护独立的连续写失败计数，作为真正的设备级熔断依据。

def _load_fuse_max() -> int:
    """安全解析熔断阈值：非数字/越界一律回退默认 3，绝不因环境变量崩溃或使熔断恒触发。"""
    raw = settings.get("safety_max_consecutive_errors", "3")
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return 3
    return value if value >= 1 else 3


_WRITE_FUSE_MAX = _load_fuse_max()

_write_fuse_lock = threading.Lock()
_consecutive_write_failures = 0


def _record_write_error() -> None:
    """线程安全地累加设备/网络写失败计数（validator 的计数会被下次通过校验清零）。"""
    global _consecutive_write_failures
    with safety_validator._lock:
        safety_validator.consecutive_errors += 1
    with _write_fuse_lock:
        _consecutive_write_failures += 1


def _record_write_success() -> None:
    """写入确认成功：清空连续写失败计数（成功中断失败连续）。"""
    global _consecutive_write_failures
    with _write_fuse_lock:
        _consecutive_write_failures = 0


def _write_fuse_tripped() -> bool:
    """连续写失败是否已达熔断阈值（需人工确认后 reset_fuse 才可继续写入）。"""
    global _consecutive_write_failures
    with _write_fuse_lock:
        return _consecutive_write_failures >= _WRITE_FUSE_MAX


def _reset_write_fuse() -> None:
    """清空 server 侧连续写失败计数（仅由 modbus_reset_fuse 在消费确认令牌后调用）。"""
    global _consecutive_write_failures
    with _write_fuse_lock:
        _consecutive_write_failures = 0


def get_client() -> ModbusTcpClient:
    global _client
    try:
        port = int(settings.modbus_port)
    except (TypeError, ValueError):
        raise RuntimeError("MODBUS_PORT 配置无效（必须为数字端口）")
    with _client_lock:
        if _client is not None and not _client.connected:
            try:
                _client.close()
            except Exception:
                pass
            _client = None
        if _client is None:
            client = ModbusTcpClient(
                host=settings.modbus_host,
                port=port,
                timeout=_MODBUS_TIMEOUT,
                retries=_MODBUS_RETRIES,
            )
            if not client.connect():
                raise ConnectionError(f"Modbus 连接失败: {settings.modbus_host}:{port}")
            _client = client
        return _client


def _reset_client() -> None:
    """丢弃缓存客户端引用，下次调用时重建连接。

    不在锁内立即 close()：并发工具调用可能正通过 asyncio.to_thread 使用该客户端
    （锁不保护 get_client 返回后客户端存活），提前 close 会让其它在途调用虚假失败。
    被丢弃的客户端在最后引用释放后由 GC 关闭底层 socket。
    """
    global _client
    with _client_lock:
        _client = None


def _confirmation_device_id() -> str:
    return f"modbus:{settings.modbus_host}:{settings.modbus_port}:unit-1"


# ===== 阶段1：读取 =====

@mcp.tool()
async def read_coil(address: int, count: int = 1, auth_token: str = "") -> dict:
    """读取线圈（%QX 输出），count>1 时批量返回 values 列表"""
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "modbus")
    param_err = _validate_read_params("coil", address, count, _MODBUS_MAX_READ_BITS)
    if param_err:
        return {"address": address, "type": "coil", "error": param_err}
    try:
        c = await asyncio.to_thread(get_client)
        rr = await asyncio.to_thread(c.read_coils, address, count=count, device_id=1)
        if rr.isError():
            audit.log("read", f"coil.{address}", "", operator=actor, success=False, detail=str(rr))
            return {"address": address, "type": "coil", "status": "error",
                    "error": _READ_ERROR}
        bits = list(rr.bits)
        audit.log("read", f"coil.{address}", str(bits), operator=actor, success=True)
        if count == 1:
            return {"address": address, "type": "coil", "value": bits[0] if bits else None}
        return {"address": address, "type": "coil", "count": count, "values": bits}
    except Exception as e:
        _reset_client()
        try:
            audit.log("read", f"coil.{address}", "", operator=actor, success=False, detail=str(e))
        except Exception:
            # 审计链缺口不得静默吞掉：计入熔断并告警（与写路径行为一致）
            _record_write_error()
            print(f"[modbus] read_coil 审计记录失败: {e}", file=sys.stderr)
        return {"address": address, "type": "coil", "status": "error",
                "error": _READ_ERROR}


@mcp.tool()
async def read_register(address: int, count: int = 1, auth_token: str = "") -> dict:
    """读取保持寄存器"""
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "modbus")
    param_err = _validate_read_params("register", address, count, _MODBUS_MAX_READ_REGISTERS)
    if param_err:
        return {"address": address, "type": "register", "error": param_err}
    try:
        c = await asyncio.to_thread(get_client)
        rr = await asyncio.to_thread(c.read_holding_registers, address, count=count, device_id=1)
        if rr.isError():
            audit.log("read", f"reg.{address}", "", operator=actor, success=False, detail=str(rr))
            return {"address": address, "type": "register", "status": "error",
                    "error": _READ_ERROR}
        vals = list(rr.registers)
        audit.log("read", f"reg.{address}", str(vals), operator=actor, success=True)
        return {"address": address, "type": "register", "count": count, "values": vals}
    except Exception as e:
        _reset_client()
        try:
            audit.log("read", f"reg.{address}", "", operator=actor, success=False, detail=str(e))
        except Exception:
            # 审计链缺口不得静默吞掉：计入熔断并告警（与写路径行为一致）
            _record_write_error()
            print(f"[modbus] read_register 审计记录失败: {e}", file=sys.stderr)
        return {"address": address, "type": "register", "status": "error",
                "error": _READ_ERROR}


@mcp.tool()
async def read_discrete_input(address: int, count: int = 1, auth_token: str = "") -> dict:
    """读取离散输入（%IX 传感器），count>1 时批量返回 values 列表"""
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "modbus")
    param_err = _validate_read_params("input", address, count, _MODBUS_MAX_READ_BITS)
    if param_err:
        return {"address": address, "type": "discrete_input", "error": param_err}
    try:
        c = await asyncio.to_thread(get_client)
        rr = await asyncio.to_thread(c.read_discrete_inputs, address, count=count, device_id=1)
        if rr.isError():
            audit.log("read", f"input.{address}", "", operator=actor, success=False, detail=str(rr))
            return {"address": address, "type": "discrete_input", "status": "error",
                    "error": _READ_ERROR}
        bits = list(rr.bits)
        audit.log("read", f"input.{address}", str(bits), operator=actor, success=True)
        if count == 1:
            return {"address": address, "type": "discrete_input",
                    "value": bits[0] if bits else None}
        return {"address": address, "type": "discrete_input", "count": count, "values": bits}
    except Exception as e:
        _reset_client()
        try:
            audit.log("read", f"input.{address}", "", operator=actor, success=False, detail=str(e))
        except Exception:
            # 审计链缺口不得静默吞掉：计入熔断并告警（与写路径行为一致）
            _record_write_error()
            print(f"[modbus] read_discrete_input 审计记录失败: {e}", file=sys.stderr)
        return {"address": address, "type": "discrete_input", "status": "error",
                "error": _READ_ERROR}


# ===== 阶段2：写入（带安全校验）=====

@mcp.tool()
async def write_coil(
    address: int,
    value: bool,
    operator: str = "ai-agent",
    auth_token: str = "",
    confirmation_token: str = "",
) -> dict:
    """写入线圈（%QX 输出）"""
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "modbus")
    tag = f"coil.{address}"
    param_err = _validate_write_params("coil", address, value)
    if param_err:
        audit.log("write_blocked", tag, str(value), operator=actor,
                  success=False, detail=param_err)
        return {"address": address, "type": "coil", "status": "blocked", "reason": param_err}
    safety_name = _safety_tag_name("coil", address)
    result = safety_validator.validate(safety_name or tag, value)
    if not result.allowed:
        audit.log("write_blocked", tag, str(value), operator=actor,
                  success=False, detail=result.reason)
        return {"address": address, "type": "coil", "status": "blocked", "reason": result.reason}
    # 设备/网络写失败熔断：连续失败达到阈值后拒绝新写入，直到人工确认后 reset_fuse
    if _write_fuse_tripped():
        reason = "熔断: 连续写入失败，需人工确认后调用 modbus_reset_fuse 重置"
        audit.log("write_blocked", tag, str(value), operator=actor,
                  success=False, detail=reason)
        return {"address": address, "type": "coil", "status": "blocked", "reason": reason}
    # 影子仿真在消费人工确认令牌之前执行：仿真拒绝时不烧掉一次性令牌
    sim_result = await shadow_sim.simulate_write(safety_name or tag, value)
    if not sim_result.safe:
        audit.log("shadow_rejected", tag, str(value), operator=actor,
                  success=False, detail=sim_result.reason)
        return {"address": address, "type": "coil", "status": "blocked", "reason": sim_result.reason}
    # 未配置安全语义映射的地址：fail-closed，必须人工确认后才允许写入
    if result.needs_confirmation or safety_name is None:
        if not confirmation_token:
            if safety_name is None:
                reason = "需要人工确认: 地址未配置安全语义映射"
            else:
                reason = f"需要人工确认: {result.reason}"
            audit.log("write_blocked", tag, str(value), operator=actor,
                      success=False, detail=reason)
            return {"address": address, "type": "coil", "status": "blocked", "reason": reason}
        try:
            confirmation_service.consume(
                confirmation_token,
                operator=actor,
                target=tag,
                value=value,
                device_id=_confirmation_device_id(),
            )
        except ConfirmationError as exc:
            reason = str(exc)
            audit.log("write_blocked", tag, str(value), operator=actor,
                      success=False, detail=reason)
            return {"address": address, "type": "coil", "status": "blocked", "reason": reason}

    try:
        audit.begin_control_operation(
            "modbus.write_coil", tag, actor,
            {"address": address, "value": value, "unit_id": 1},
        )
        c = await asyncio.to_thread(get_client)
        r = await asyncio.to_thread(c.write_coil, address, value, device_id=1)
        ok = not r.isError()
        # 读回验证：确认写入已在设备端生效（读回失败不判失败，避免超时误报）
        if ok:
            try:
                rb = await asyncio.to_thread(c.read_coils, address, count=1, device_id=1)
                if not rb.isError() and rb.bits and bool(rb.bits[0]) != bool(value):
                    ok = False
            except Exception:
                pass
        try:
            audit.log("write", tag, str(value), operator=actor, success=ok)
        except Exception:
            _record_write_error()
            return {"address": address, "type": "coil", "value": value,
                    "status": "error",
                    "error": "写入已执行但审计记录失败（已计入熔断，需人工介入）"}
        if ok:
            _record_write_success()
        else:
            # 读回校验未确认（写入已执行但设备端未生效）：计入熔断
            _record_write_error()
        return {"address": address, "type": "coil", "value": value,
                "status": "ok" if ok else "error"}
    except Exception as e:
        _reset_client()
        _record_write_error()
        try:
            audit.log("write", tag, str(value), operator=actor,
                      success=False, detail=str(e))
        except Exception:
            pass
        return {"address": address, "type": "coil", "status": "error",
                "error": _WRITE_ERROR}


@mcp.tool()
async def write_register(
    address: int,
    value: int,
    operator: str = "ai-agent",
    auth_token: str = "",
    confirmation_token: str = "",
) -> dict:
    """写入保持寄存器"""
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "modbus")
    tag = f"register.{address}"
    param_err = _validate_write_params("register", address, value)
    if param_err:
        audit.log("write_blocked", tag, str(value), operator=actor,
                  success=False, detail=param_err)
        return {"address": address, "type": "register", "status": "blocked", "reason": param_err}
    safety_name = _safety_tag_name("register", address)
    result = safety_validator.validate(safety_name or tag, value)
    if not result.allowed:
        audit.log("write_blocked", tag, str(value), operator=actor,
                  success=False, detail=result.reason)
        return {"address": address, "type": "register", "status": "blocked", "reason": result.reason}
    # 设备/网络写失败熔断：连续失败达到阈值后拒绝新写入，直到人工确认后 reset_fuse
    if _write_fuse_tripped():
        reason = "熔断: 连续写入失败，需人工确认后调用 modbus_reset_fuse 重置"
        audit.log("write_blocked", tag, str(value), operator=actor,
                  success=False, detail=reason)
        return {"address": address, "type": "register", "status": "blocked", "reason": reason}
    # 影子仿真在消费人工确认令牌之前执行：仿真拒绝时不烧掉一次性令牌
    sim_result = await shadow_sim.simulate_write(safety_name or tag, value)
    if not sim_result.safe:
        audit.log("shadow_rejected", tag, str(value), operator=actor,
                  success=False, detail=sim_result.reason)
        return {"address": address, "type": "register", "status": "blocked", "reason": sim_result.reason}
    # 未配置安全语义映射的地址：fail-closed，必须人工确认后才允许写入
    if result.needs_confirmation or safety_name is None:
        if not confirmation_token:
            if safety_name is None:
                reason = "需要人工确认: 地址未配置安全语义映射"
            else:
                reason = f"需要人工确认: {result.reason}"
            audit.log("write_blocked", tag, str(value), operator=actor,
                      success=False, detail=reason)
            return {"address": address, "type": "register", "status": "blocked", "reason": reason}
        try:
            confirmation_service.consume(
                confirmation_token,
                operator=actor,
                target=tag,
                value=value,
                device_id=_confirmation_device_id(),
            )
        except ConfirmationError as exc:
            reason = str(exc)
            audit.log("write_blocked", tag, str(value), operator=actor,
                      success=False, detail=reason)
            return {"address": address, "type": "register", "status": "blocked", "reason": reason}

    try:
        audit.begin_control_operation(
            "modbus.write_register", tag, actor,
            {"address": address, "value": value, "unit_id": 1},
        )
        c = await asyncio.to_thread(get_client)
        r = await asyncio.to_thread(c.write_register, address, value, device_id=1)
        ok = not r.isError()
        # 读回验证：确认写入已在设备端生效（读回失败不判失败，避免超时误报）
        if ok:
            try:
                rb = await asyncio.to_thread(c.read_holding_registers, address, count=1, device_id=1)
                if not rb.isError() and rb.registers and rb.registers[0] != value:
                    ok = False
            except Exception:
                pass
        try:
            audit.log("write", tag, str(value), operator=actor, success=ok)
        except Exception:
            _record_write_error()
            return {"address": address, "type": "register", "value": value,
                    "status": "error",
                    "error": "写入已执行但审计记录失败（已计入熔断，需人工介入）"}
        if ok:
            _record_write_success()
        else:
            # 读回校验未确认（写入已执行但设备端未生效）：计入熔断
            _record_write_error()
        return {"address": address, "type": "register", "value": value,
                "status": "ok" if ok else "error"}
    except Exception as e:
        _reset_client()
        _record_write_error()
        try:
            audit.log("write", tag, str(value), operator=actor,
                      success=False, detail=str(e))
        except Exception:
            pass
        return {"address": address, "type": "register", "status": "error",
                "error": _WRITE_ERROR}


@mcp.tool()
async def scan_devices(auth_token: str = "") -> list[dict]:
    """扫描 Modbus 网络设备（online=正常响应；offline=异常响应帧；error=连接/超时失败）"""
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "modbus")
    devices = []
    for slave_id in range(1, 11):
        status = "offline"
        detail = ""
        try:
            c = await asyncio.to_thread(get_client)
            rr = await asyncio.to_thread(
                c.read_holding_registers, 0, count=1, device_id=slave_id
            )
            if not rr.isError():
                status = "online"
            else:
                detail = str(rr)
        except Exception as exc:
            # 单个从站超时/通信异常不重置共享连接：_reset_client 会丢弃其它并发
            # 调用正在使用的客户端，且每从站重连放大耗时；连接级故障由下次
            # get_client 的 connected 检查自动重建。
            status = "error"
            detail = str(exc)
        devices.append({"slave_id": slave_id, "status": status})
        # 审计记录与从站状态判定分离：审计失败不得被误判为从站通信异常
        try:
            audit.log("scan", f"modbus.slave.{slave_id}", status,
                      operator=actor, success=status == "online",
                      detail=detail)
        except Exception:
            pass
    return devices


@mcp.tool()
async def modbus_reset_fuse(auth_token: str = "", confirmation_token: str = "") -> str:
    """重置安全熔断器（连续写入失败后自动触发熔断，需人工确认令牌）

    Args:
        auth_token: 认证令牌
        confirmation_token: 一次性人工确认令牌（必须为 fuse_reset 用途签发）

    安全机制:
        熔断的意义在于异常后强制人工介入。没有人工确认令牌就能远程重置，
        熔断机制就形同虚设，因此必须消费一次性令牌后才允许重置。
    """
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "modbus")
    if not confirmation_token:
        reason = "重置熔断器需要一次性人工确认令牌"
        try:
            audit.log("fuse_reset_blocked", "modbus.fuse_reset", "", operator=actor,
                      success=False, detail=reason)
        except Exception:
            pass
        return f"🚫 {reason}"
    try:
        confirmation_service.consume(
            confirmation_token,
            operator=actor,
            target="modbus.fuse_reset",
            value="reset",
            device_id=_confirmation_device_id(),
        )
    except ConfirmationError as exc:
        try:
            audit.log("fuse_reset_blocked", "modbus.fuse_reset", "", operator=actor,
                      success=False, detail=str(exc))
        except Exception:
            pass
        return f"🚫 熔断器重置被拒绝: {exc}"
    safety_validator.reset_fuse()
    _reset_write_fuse()
    try:
        audit.log("fuse_reset", "modbus.fuse_reset", "reset", operator=actor)
    except Exception:
        # 熔断已实际重置（副作用先于审计），审计失败不能把内部路径抛给客户端：
        # 计入熔断并显式告知，需人工核实重置事件（与写路径的审计失败处理一致）。
        _record_write_error()
        return "⚠️ 熔断器已重置，但审计记录失败（已计入熔断，需人工核实）"
    return "✅ 熔断器已重置"


if __name__ == "__main__":
    mcp.run()
