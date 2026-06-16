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
from _helpers import mcp
from s7_adapter import adapter

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
    _logger.critical("影子仿真模块加载失败！所有写入操作将被拒绝。")
    shadow_sim = None

# ── 审计日志 ──
try:
    from mcp_common.audit import get_audit_logger
    _audit = get_audit_logger()
except ImportError:
    _audit = None
    _logger.warning("审计日志模块不可用")


@mcp.tool(
    name="s7_connect",
    annotations={"destructiveHint": False},
)
def s7_connect(ip: str = "192.168.0.110", rack: int = 0, slot: int = 1) -> str:
    """连接到西门子 PLC (S7 协议)

    Args:
        ip: PLC IP 地址（PLCSIM 默认 192.168.0.110）
        rack: 机架号（默认 0）
        slot: 插槽号（默认 1）
    """
    return adapter.connect(ip, rack, slot)


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
async def s7_write(address: str, value: str) -> str:
    """通过 S7 协议写入 PLC 变量（带安全互锁）

    Args:
        address: PLC 地址（同 s7_read 支持的格式）
        value: 要写入的值（字符串形式，自动类型转换）

    安全机制:
        - 仅限非急停/非安全标签
        - 数值范围检查
        - 异常跳变检测
        - 连续异常自动熔断
        - 影子仿真验证
        - 审计日志记录
    """
    # 安全模块不可用时，拒绝所有写入
    if not SAFETY_AVAILABLE or safety_val is None:
        return "🚫 写入被拒绝: 安全模块不可用，无法执行安全校验"

    try:
        # 1. 互锁校验
        result = safety_val.validate(address, value)
        if not result.allowed:
            if _audit:
                _audit.log("write_rejected", address, value, success=False, detail=result.reason)
            return f"🚫 写入被拒绝: {result.reason}"

        # 2. 影子仿真验证
        if shadow_sim is not None:
            try:
                numeric_value = float(value)
            except (ValueError, TypeError):
                numeric_value = value
            sim_result = await shadow_sim.simulate_write(address, numeric_value)
            if not sim_result.safe:
                if _audit:
                    _audit.log("shadow_rejected", address, value, success=False, detail=sim_result.reason)
                return f"🚫 影子仿真拒绝: {sim_result.reason}"

        # 3. 执行写入
        write_result = adapter.write_address(address, value)

        # 4. 审计日志
        if _audit:
            _audit.log("write", address, value, success=True)

        return write_result
    except ConnectionError as e:
        if _audit:
            _audit.log("write_error", address, value, success=False, detail=str(e))
        return f"❌ {e}"
    except Exception as e:
        if _audit:
            _audit.log("write_error", address, value, success=False, detail=str(e))
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
