"""
S7 运行时读写工具 — MCP 工具注册

通过 python-snap7 直接读写 PLC（PLCSIM / 真机），不需要 TIA Portal。

工具:
  - s7_connect       — 连接到 PLC
  - s7_disconnect    — 断开 PLC 连接
  - s7_read          — 按地址读取（支持 M/MB/MW/MD/DB）
  - s7_write         — 按地址写入（带安全互锁检查）
  - s7_read_status   — 读取连接状态和 CPU 状态

依赖:
  python-snap7, 以及运行中的 PLCSIM / 真机 S7-1200/1500
"""
import logging
from _helpers import mcp, PLC_IP
from s7_adapter import S7Adapter, adapter
from mcp_common.control_target import TargetConfigurationError, require_control_ip

# ── 安全模块加载 ──
_logger = logging.getLogger(__name__)
SAFETY_AVAILABLE = False
try:
    from safety.validator import validator as safety_val
    SAFETY_AVAILABLE = True
except ImportError:
    _logger.critical("安全模块加载失败！所有写入操作将被拒绝。请确保 safety/ 目录可访问。")
    safety_val = None

try:
    from safety.shadow_simulator import shadow_sim
except ImportError:
    _logger.critical("静态预检模块加载失败！所有写入操作将被拒绝。")
    shadow_sim = None

from safety.confirmation import ConfirmationError, ConfirmationService
confirmation_service = ConfirmationService()

# ── 审计日志（强制） ──
from mcp_common.audit import get_audit_logger
_audit = get_audit_logger()

# ── 注册 bit_reader（require_bits 安全前置条件检查） ──
if SAFETY_AVAILABLE:
    def _read_safety_bit(address: str):
        """读取 PLC 安全位，用于 require_bits 互锁检查"""
        if not adapter.is_connected:
            return None
        try:
            val = adapter.read_address(address)
            return bool(val)
        except Exception:
            return None
    safety_val.set_bit_reader(_read_safety_bit)


def _confirmation_device_id() -> str:
    device_id = getattr(adapter, "device_id", "")
    if not isinstance(device_id, str) or not device_id:
        raise ConfirmationError("S7 目标身份未知")
    return device_id


@mcp.tool(
    name="s7_connect",
    annotations={"destructiveHint": False},
)
def s7_connect(ip: str = "", rack: int = 0, slot: int = 1) -> str:
    """连接到西门子 PLC (S7 协议)

    Args:
        ip: 仅允许为空或唯一隔离 PLCSIM 目标地址
        rack: 机架号（默认 0）
        slot: 插槽号（默认 1）
    """
    try:
        target = require_control_ip(ip or PLC_IP)
    except TargetConfigurationError as exc:
        return f"🚫 连接被拒绝: {exc}"
    return adapter.connect(target.plc_ip, rack, slot)


@mcp.tool(
    name="s7_disconnect",
    annotations={"destructiveHint": False},
)
def s7_disconnect() -> str:
    """断开当前 PLC 连接"""
    return adapter.disconnect()


@mcp.tool(
    name="s7_read",
    annotations={"readOnlyHint": True},
)
def s7_read(address: str) -> str:
    """通过 S7 协议读取 PLC 变量的值

    Args:
        address: PLC 地址，支持格式:
                 M0.0      — 位 (Merker)
                 MB0       — 字节
                 MW10      — 字 (int)
                 MD20      — 双字 (real)
                 DB1.MW10  — DB 块中的字

    用法示例:
        s7_read("M0.0")        # 读取 M0.0 位
        s7_read("MW10")        # 读取 MW10 整数
        s7_read("MD20")        # 读取 MD20 浮点数
        s7_read("DB1.MW10")    # 读取 DB1.MW10
    """
    try:
        value = adapter.read_address(address)
        return f"📍 {address} = {value}"
    except ConnectionError as e:
        return f"❌ {e}"
    except Exception as e:
        return f"❌ 读取失败 [{address}]: {e}"


@mcp.tool(
    name="s7_write",
    annotations={"destructiveHint": True},
)
async def s7_write(
    address: str,
    value: str,
    operator: str = "ai-agent",
    confirmation_token: str = "",
) -> str:
    """通过 S7 协议写入 PLC 变量（带安全互锁）

    Args:
        address: PLC 地址（同 s7_read 支持的格式）
        value: 要写入的值（字符串形式，自动类型转换）

    安全机制:
        - 仅限非急停/非安全标签
        - 数值范围检查
        - 异常跳变检测
        - 连续异常自动熔断
        - 静态预检（不模拟 PLC 扫描周期或真实逻辑，不能代替真实仿真）
        - 审计日志记录
    """
    # 安全模块不可用时，拒绝所有写入
    if not SAFETY_AVAILABLE or safety_val is None:
        return "🚫 写入被拒绝: 安全模块不可用，无法执行安全校验"

    # 静态预检模块不可用时，拒绝所有写入（安全红线）
    if shadow_sim is None:
        return "🚫 写入被拒绝: 静态预检模块不可用（违反安全红线），请检查 safety/ 目录"

    try:
        # S7 MCP 尚未提供已认证会话上下文；生产环境会由审计闸门拒绝
        # 空主体，避免把调用方自报的 operator 伪装成可信身份。
        audit_actor = ""
        # 0. 原始地址必须显式映射到安全语义；不能靠地址字符串绕过联锁。
        canonical_address = S7Adapter.canonicalize_address(address)
        mapping = safety_val.resolve_s7_write_address(canonical_address)
        if mapping is None:
            reason = f"未映射的允许写入地址: {canonical_address}"
            _audit.log("write_rejected", canonical_address, str(value), success=False, detail=reason)
            return f"🚫 写入被拒绝: {reason}"

        expected_type = S7Adapter.address_value_type(canonical_address)
        if mapping["type"] != expected_type:
            reason = f"地址映射类型不匹配: {canonical_address}（{mapping['type']} != {expected_type}）"
            _audit.log("write_rejected", canonical_address, str(value), success=False, detail=reason)
            return f"🚫 写入被拒绝: {reason}"

        try:
            numeric_value = adapter.parse_write_value(canonical_address, value)
        except ValueError as exc:
            reason = f"写入值类型无效: {exc}"
            _audit.log("write_rejected", canonical_address, str(value), success=False, detail=reason)
            return f"🚫 写入被拒绝: {reason}"

        # 1. 读取当前值（用于跳变检测）
        try:
            current_value = adapter.read_address(canonical_address)
        except Exception:
            current_value = None

        # 2. 互锁校验
        semantic_target = mapping["target"]
        result = safety_val.validate(semantic_target, numeric_value, current_value=current_value)
        if not result.allowed:
            _audit.log("write_rejected", canonical_address, str(value), success=False, detail=result.reason)
            return f"🚫 写入被拒绝: {result.reason}"
        if result.needs_confirmation:
            if not confirmation_token:
                reason = f"需要人工确认: {result.reason}"
                _audit.log("write_rejected", canonical_address, str(value), success=False, detail=reason)
                return f"🚫 写入被拒绝: {reason}"
            try:
                confirmation_service.consume(
                    confirmation_token,
                    operator=operator,
                    target=canonical_address,
                    value=numeric_value,
                    device_id=_confirmation_device_id(),
                )
            except ConfirmationError as exc:
                reason = str(exc)
                _audit.log("write_rejected", canonical_address, str(value), success=False, detail=reason)
                return f"🚫 写入被拒绝: {reason}"

        # 3. 静态预检不模拟 PLC 扫描周期或真实逻辑，不能代替隔离 PLCSIM 验收。
        sim_result = await shadow_sim.simulate_write(semantic_target, numeric_value, current_value=current_value)
        if not sim_result.safe:
            _audit.log("static_precheck_rejected", canonical_address, str(value), success=False, detail=sim_result.reason)
            return f"🚫 静态预检拒绝: {sim_result.reason}"

        # 4. 执行写入
        _audit.begin_control_operation(
            "s7.write", canonical_address, audit_actor,
            {"address": canonical_address, "value": numeric_value, "semantic_target": semantic_target},
        )
        write_result = adapter.write_address(canonical_address, numeric_value)

        # 5. 审计日志
        _audit.log("write", canonical_address, str(numeric_value), operator=audit_actor,
                   success=True, detail=f"semantic_target={semantic_target}")

        return write_result
    except ConnectionError as e:
        _audit.log("write_error", address, str(value), success=False, detail=str(e))
        return f"❌ {e}"
    except Exception as e:
        _audit.log("write_error", address, str(value), success=False, detail=str(e))
        return f"❌ 写入失败 [{address}={value}]: {e}"


@mcp.tool(
    name="s7_status",
    annotations={"readOnlyHint": True},
)
def s7_status() -> str:
    """获取 S7 连接状态"""
    if not adapter.is_connected:
        return "🔴 未连接"
    try:
        state = adapter._client.get_cpu_state()
        return f"🟢 已连接 | CPU 状态: {state}"
    except Exception:
        return "🟡 已连接（无法读取 CPU 状态）"
