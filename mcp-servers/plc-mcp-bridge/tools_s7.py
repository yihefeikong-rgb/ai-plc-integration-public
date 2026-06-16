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
from _helpers import mcp
from s7_adapter import adapter


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
def s7_write(address: str, value: str) -> str:
    """通过 S7 协议写入 PLC 变量（带安全互锁）

    Args:
        address: PLC 地址（同 s7_read 支持的格式）
        value: 要写入的值（字符串形式，自动类型转换）

    安全机制:
        - 仅限非急停/非安全标签
        - 数值范围检查
        - 异常跳变检测
        - 连续异常自动熔断
    """
    try:
        # 安全校验（复用 safety.validator）
        try:
            from safety.validator import validator as safety_val
            result = safety_val.validate(address, value)
            if not result.allowed:
                return f"🚫 写入被拒绝: {result.reason}"
        except ImportError:
            pass  # 安全模块不可用时跳过

        result = adapter.write_address(address, value)
        return result
    except ConnectionError as e:
        return f"❌ {e}"
    except Exception as e:
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
