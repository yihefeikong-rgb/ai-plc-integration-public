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
import asyncio
import hmac
import logging
import os
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
from mcp_common.audit import (
    AuditConfigurationError,
    AuditStorageError,
    authenticated_actor,
    get_audit_logger,
)
_audit = get_audit_logger()

# ── 注册 bit_reader（require_bits 安全前置条件检查） ──
if SAFETY_AVAILABLE:
    def _read_safety_bit(address: str):
        """读取 PLC 安全位，用于 require_bits 互锁检查"""
        if not adapter.is_connected:
            _logger.warning("安全位读取跳过: PLC 未连接 (%s)", address)
            return None
        try:
            val = adapter.read_address(address)
            return bool(val)
        except Exception:
            _logger.error("安全位读取失败: %s", address, exc_info=True)
            return None
    safety_val.set_bit_reader(_read_safety_bit)


def _confirmation_device_id() -> str:
    device_id = getattr(adapter, "device_id", "")
    if not isinstance(device_id, str) or not device_id:
        raise ConfirmationError("S7 目标身份未知")
    return device_id


def _authenticated_actor() -> str:
    """从共享 MCP 认证令牌派生审计/确认主体；未配置时返回空串。

    与签发端（ai-plc-assistant/backend/routes/orchestrator.py）按
    authenticated_actor(MCP_AUTH_TOKEN, namespace) 推导写入方身份的方式一致。
    空主体在显式生产环境中会被审计闸门拒绝（fail-closed）。
    """
    token = os.environ.get("MCP_AUTH_TOKEN", "")
    if not token:
        return ""
    return authenticated_actor(token, "s7")


def _require_auth(token: str = "") -> str:
    """验证 auth token 并派生可审计主体（fail-closed）。

    认证门必须依赖调用方显式提供的凭据：
    - 未配置 MCP_AUTH_TOKEN 时拒绝一切写入；
    - 调用方省略/伪造 auth_token 一律拒绝，绝不回退到服务器自身令牌
      （此前 effective = token or expected 使空 token 恒通过认证，门禁失效）；
    - 通过校验后派生可审计主体，绑定到确认令牌消费与审计。
    """
    expected = os.environ.get("MCP_AUTH_TOKEN", "")
    if not expected:
        raise PermissionError("MCP_AUTH_TOKEN 未配置，服务不可用")
    if not isinstance(token, str) or not token:
        raise PermissionError("认证失败：缺少 auth token")
    if not hmac.compare_digest(token, expected):
        raise PermissionError("认证失败：无效的 auth token")
    return authenticated_actor(token, "s7")


def _log_audit_failure(target: str, value, detail: str) -> None:
    """尽力记录失败审计；审计链自身不可用时只写服务端日志，避免二次抛出。"""
    try:
        _audit.log("write_error", target, str(value), success=False, detail=detail)
    except Exception:
        _logger.error("s7 失败审计写入失败", exc_info=True)


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
    except ConnectionError:
        _logger.error("s7_read 连接异常", exc_info=True)
        return "❌ 读取失败: PLC 连接异常（详见服务端日志）"
    except Exception:
        _logger.error("s7_read 读取异常", exc_info=True)
        return f"❌ 读取失败 [{address}]（详见服务端日志）"


@mcp.tool(
    name="s7_write",
    annotations={"destructiveHint": True},
)
async def s7_write(
    address: str,
    value: str,
    operator: str = "ai-agent",
    auth_token: str = "",
    confirmation_token: str = "",
) -> str:
    """通过 S7 协议写入 PLC 变量（带安全互锁）

    Args:
        address: PLC 地址（同 s7_read 支持的格式）
        value: 要写入的值（字符串形式，自动类型转换）
        auth_token: 认证令牌（须与服务器配置的 MCP_AUTH_TOKEN 一致；
                    未配置或令牌无效时拒绝写入，fail-closed）

    安全机制:
        - 仅限非急停/非安全标签
        - 数值范围检查
        - 异常跳变检测（当前值读取失败时拒绝写入，不静默跳过）
        - 连续异常自动熔断
        - 静态预检（不模拟 PLC 扫描周期或真实逻辑，不能代替真实仿真）
        - 人工确认令牌（一次性、绑定语义目标与操作者身份）
        - 审计日志记录

    Notes:
        snap7 网络往返、确认令牌消费与审计文件锁均在线程池执行，
        避免一次写入长时间冻结事件循环。
    """
    # 安全模块不可用时，拒绝所有写入
    if not SAFETY_AVAILABLE or safety_val is None:
        return "🚫 写入被拒绝: 安全模块不可用，无法执行安全校验"

    # 静态预检模块不可用时，拒绝所有写入（安全红线）
    if shadow_sim is None:
        return "🚫 写入被拒绝: 静态预检模块不可用（违反安全红线），请检查 safety/ 目录"

    # 认证（fail-closed）：与其他 MCP 写入工具一致，s7_write 必须通过
    # _require_auth 门禁。未配置 MCP_AUTH_TOKEN 或令牌无效时直接拒绝，
    # 绝不把调用方自报的 operator 绑定到确认令牌消费或审计主体。
    audit_actor = _require_auth(auth_token)

    # 0. 原始地址必须显式映射到安全语义；不能靠地址字符串绕过联锁。
    try:
        canonical_address = S7Adapter.canonicalize_address(address)
    except ValueError as exc:
        reason = f"无效地址: {exc}"
        _audit.log("write_rejected", str(address), str(value), success=False, detail=reason)
        return f"🚫 写入被拒绝: {reason}"

    mapping = safety_val.resolve_s7_write_address(canonical_address)
    if mapping is None:
        reason = f"未映射的允许写入地址: {canonical_address}"
        _audit.log("write_rejected", canonical_address, str(value), success=False, detail=reason)
        return f"🚫 写入被拒绝: {reason}"

    semantic_target = mapping["target"]

    # 1. 地址类型与规则映射一致；值严格按物理地址类型解析
    try:
        expected_type = S7Adapter.address_value_type(canonical_address)
        if mapping["type"] != expected_type:
            reason = f"地址映射类型不匹配: {canonical_address}（{mapping['type']} != {expected_type}）"
            _audit.log("write_rejected", canonical_address, str(value), success=False, detail=reason)
            return f"🚫 写入被拒绝: {reason}"
        numeric_value = adapter.parse_write_value(canonical_address, value)
    except ValueError as exc:
        reason = f"写入值类型无效: {exc}"
        _audit.log("write_rejected", canonical_address, str(value), success=False, detail=reason)
        return f"🚫 写入被拒绝: {reason}"

    # 2. 读取当前值（用于跳变检测）。读取失败必须 fail-closed：
    #    不能静默吞掉异常后跳过 10 倍跳变检测继续写入。
    try:
        current_value = await asyncio.to_thread(adapter.read_address, canonical_address)
    except ConnectionError:
        reason = "无法读取当前值（PLC 未连接），拒绝写入"
        _logger.error("s7_write 读取当前值失败: PLC 未连接", exc_info=True)
        _audit.log("write_rejected", canonical_address, str(value), success=False, detail=reason)
        return f"🚫 写入被拒绝: {reason}"
    except Exception:
        reason = "无法读取当前值，跳变检测无法执行，拒绝写入"
        _logger.error("s7_write 读取当前值失败", exc_info=True)
        _audit.log("write_rejected", canonical_address, str(value), success=False, detail=reason)
        return f"🚫 写入被拒绝: {reason}"

    # 3. 互锁校验（含 require_bits 安全前置条件读取；在线程池执行，避免阻塞事件循环）
    result = await asyncio.to_thread(
        safety_val.validate, semantic_target, numeric_value, current_value=current_value
    )
    if not result.allowed:
        _audit.log("write_rejected", canonical_address, str(value), success=False, detail=result.reason)
        return f"🚫 写入被拒绝: {result.reason}"
    if result.needs_confirmation and not confirmation_token:
        reason = f"需要人工确认: {result.reason}"
        _audit.log("write_rejected", canonical_address, str(value), success=False, detail=reason)
        return f"🚫 写入被拒绝: {reason}"

    # 4. 静态预检不模拟 PLC 扫描周期或真实逻辑，不能代替隔离 PLCSIM 验收。
    sim_result = await shadow_sim.simulate_write(semantic_target, numeric_value, current_value=current_value)
    if not sim_result.safe:
        _audit.log("static_precheck_rejected", canonical_address, str(value), success=False, detail=sim_result.reason)
        return f"🚫 静态预检拒绝: {sim_result.reason}"

    # 5. 所有校验通过后、紧邻真实写入时才消费一次性人工确认令牌：
    #    - token target 绑定语义目标（与签发端 orchestrator.py 的
    #      check_write(body.target) / issue(target=body.target) 一致），
    #      绑定物理地址会导致签发端签发的令牌永远无法被消费；
    #    - 在互锁/预检被拒之前不消费，避免令牌被白白烧掉。
    if result.needs_confirmation:
        try:
            await asyncio.to_thread(
                confirmation_service.consume,
                confirmation_token,
                operator=audit_actor,
                target=semantic_target,
                value=numeric_value,
                device_id=_confirmation_device_id(),
            )
        except ConfirmationError as exc:
            reason = f"人工确认无效: {exc}"
            _audit.log("write_rejected", canonical_address, str(value), success=False, detail=reason)
            return f"🚫 写入被拒绝: {reason}"

    # 6. 执行写入（控制意图审计失败同样阻断写入，fail-closed）
    try:
        await asyncio.to_thread(
            _audit.begin_control_operation,
            "s7.write", canonical_address, audit_actor,
            {"address": canonical_address, "value": numeric_value, "semantic_target": semantic_target},
        )
        write_result = await asyncio.to_thread(adapter.write_address, canonical_address, numeric_value)
    except ConnectionError:
        _logger.error("s7_write 写入连接异常", exc_info=True)
        _log_audit_failure(canonical_address, value, "PLC 连接异常")
        return "❌ 写入失败: PLC 连接异常（详见服务端日志）"
    except (AuditStorageError, AuditConfigurationError):
        _logger.error("s7_write 审计链不可用，写入被阻断（fail-closed）", exc_info=True)
        return "🚫 写入被拒绝: 审计链不可用，控制操作被阻断（fail-closed）"
    except Exception as exc:
        _logger.error("s7_write 执行写入异常", exc_info=True)
        _log_audit_failure(canonical_address, value, f"写入异常: {type(exc).__name__}")
        return f"❌ 写入失败 [{address}={value}]（详见服务端日志）"

    # 7. 审计日志（写入已成功；审计记录失败时如实提示，不误报为写入失败）
    try:
        await asyncio.to_thread(
            _audit.log, "write", canonical_address, str(numeric_value),
            operator=audit_actor, success=True, detail=f"semantic_target={semantic_target}",
        )
    except (AuditStorageError, AuditConfigurationError):
        _logger.error("s7_write 写入已执行但审计记录失败", exc_info=True)
        return f"{write_result}（写入已执行，但审计记录失败，请人工核查）"
    return write_result


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
