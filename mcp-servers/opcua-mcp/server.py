#!/usr/bin/env python3
"""
OPC UA MCP Server — AI 通过 OPC UA 协议读写 PLC 变量

架构:
  AI(Claude) ←→ stdio MCP ←→ 本服务器 ←→ asyncua ←→ PLC (S7-1200/1500)

安全原则:
  - 所有写入操作必须先检查互锁条件
  - 连续 3 次异常值自动熔断
  - 所有操作记录审计日志

用法:
  python server.py              # stdio 模式（给 Claude Code 用）
  python server.py --test       # 测试连接
"""
import asyncio
import hmac
import logging
import os
import sys
from typing import Optional
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("❌ 请安装 mcp: pip install mcp", file=sys.stderr)
    sys.exit(1)

try:
    from asyncua import Client, ua
    ASYNCUA_AVAILABLE = True
except ImportError:
    ASYNCUA_AVAILABLE = False

# 导入本地安全模块（OPC UA 专用互锁检查）。
# 不得向 sys.path 插入本目录：本模块一旦被加载（包括测试以 importlib
# 加载），position 0 的污染会让其他模块的 `import server` 解析到本文件。
try:
    import opcua_safety as safety
except ModuleNotFoundError:
    import importlib.util as _ilu

    _safety_spec = _ilu.spec_from_file_location(
        "opcua_safety", Path(__file__).parent / "opcua_safety.py"
    )
    safety = _ilu.module_from_spec(_safety_spec)
    _safety_spec.loader.exec_module(safety)

# 导入根安全链（validator + shadow_sim + audit）。
# 任一依赖缺失即拒绝启动（打印友好提示后退出），避免半初始化服务带病运行。
try:
    from safety.validator import validator as safety_validator
    import safety.validator as _validator_module
    from safety.shadow_simulator import shadow_sim
    from safety.confirmation import ConfirmationError, ConfirmationService
    from mcp_common.audit import authenticated_actor, get_audit_logger
    from mcp_common.control_target import (
        TargetConfigurationError,
        approved_opcua_endpoint,
        require_opcua_endpoint,
    )
except Exception as exc:
    print(f"❌ 安全链依赖缺失，OPC UA 写入/确认/审计不可用: {exc}", file=sys.stderr)
    sys.exit(1)

_audit = get_audit_logger()
_logger = logging.getLogger(__name__)

# ── 可选 OPC UA 安全会话（格式: Policy,Mode,cert,key[,server_cert]）──
# 例如 "Basic256Sha256,SignAndEncrypt,<证书>,<私钥>"；为空时保持现有明文连接，
# 强制加密/认证需要配合 mcp_common/control_target.py 的端点策略改动（见 notes）。
_SECURITY_STRING = os.environ.get("OPCUA_SECURITY_STRING", "")

# ── 认证 ──
_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")
confirmation_service = ConfirmationService()


def _require_auth(token: str = "") -> None:
    """验证 auth token；未配置令牌时控制服务不可用。"""
    if not _AUTH_TOKEN:
        raise PermissionError("MCP_AUTH_TOKEN 未配置，服务不可用")
    if not isinstance(token, str) or not hmac.compare_digest(token, _AUTH_TOKEN):
        raise PermissionError("认证失败：无效的 auth token")


# ── 全局状态 ──
mcp = FastMCP("opcua_plc")
_client: Optional[object] = None
_endpoint: str = ""

# 连接状态锁：消除 connect/disconnect 判空与赋值之间的 TOCTOU 竞态
_conn_lock = asyncio.Lock()

# 连接代际计数：每次 connect/disconnect 变更连接时递增。并发工具在连接锁内
# 快照该计数，操作失败时据此区分"真实写入失败"与"连接生命周期变更"。
_conn_generation = 0

# require_bits 位读取缓存（validator 的位回调是同步的，须先异步预读）
_BIT_CACHE: dict[str, bool | None] = {}

# 节点 VariantType 缓存（data_type=auto 时避免每次写入重读类型）
_VTYPE_CACHE: dict[str, object] = {}

_MAX_BROWSE_DEPTH = 4
_MAX_BROWSE_NODES = 500


def _confirmation_device_id() -> str:
    if not _endpoint:
        raise ConfirmationError("OPC UA 目标身份未知")
    return f"opcua:{_endpoint}"


# ── 辅助函数 ──

def _safe_error(exc: BaseException) -> str:
    """把异常转成不泄露内部细节的摘要；完整信息写入服务端日志。"""
    return f"{type(exc).__name__}（详情见服务端日志）"


def _audit_log_safe(*args, **kwargs) -> None:
    """记录审计日志；审计存储/配置故障时降级为服务端日志，不向客户端抛裸异常。

    审计链损坏、文件不可写或生产环境缺持久密钥时（AuditStorageError /
    AuditConfigurationError），异常消息含绝对日志路径与 OS 错误文本，绝不能
    原样回传客户端绕过 _safe_error 脱敏。控制动作的 fail-closed 审计前置门
    由 begin_control_operation 单独强制，不经过本函数。
    """
    try:
        _audit.log(*args, **kwargs)
    except Exception as exc:
        _logger.warning("审计日志写入失败: %s", exc)


def _node_id_to_tag(node_id: str) -> str:
    """将 OPC UA 节点 ID 转为互锁规则使用的裸标签名。

    例如 'ns=3;s=DB1.MotorSpeed' → 'DB1.MotorSpeed'；
    非字符串标识节点（如 'ns=0;i=85'）原样返回（不会命中任何规则）。
    """
    node_id = node_id.strip()
    if node_id.lower().startswith("ns="):
        for part in node_id.split(";"):
            if part.lower().startswith("s="):
                return part[2:]
    return node_id


def _node_namespace(node_id: str) -> str:
    """从 'ns=N;...' 形式节点 ID 提取命名空间索引；无法解析时返回空串。"""
    for part in node_id.split(";"):
        if part.lower().startswith("ns="):
            idx = part.split("=", 1)[1].strip()
            if idx.isdigit():
                return idx
    return ""


def _require_bits_for(tag_name: str) -> list[str] | None:
    """返回匹配 tag_name 的互锁规则所需的全部位地址；无匹配规则返回 None。

    目标匹配大小写不敏感（与 validator 的 _rules_by_target 上键一致）：
    否则大小写变体标签写入时安全位异步预取被跳过，_BIT_CACHE 中的陈旧位值
    可能直接放行 require_bits 检查（对 check_interlock 不复查的位构成互锁旁路）。
    """
    bits: list[str] = []
    tag_upper = str(tag_name).upper()
    for rule in getattr(safety_validator, "_rules", []) or []:
        if str(rule.get("target") or "").upper() == tag_upper:
            bits.extend(rule.get("require_bits") or [])
    return list(dict.fromkeys(bits)) if bits else None


def _read_safety_bit(address: str) -> bool | None:
    """同步位读取回调（validator require_bits 检查用）：只读预读缓存，未预读到视为失败。"""
    return _BIT_CACHE.get(address, None)


async def _refresh_safety_bits(node_id: str, bit_addresses: list[str], client) -> None:
    """写入前异步预读互锁规则 require_bits 涉及的安全位。

    validator 的位读取回调是同步的、无法直接 await OPC UA 读取，
    因此先在此处用异步路径预读并缓存；任何位读取失败都缓存为 None（fail-closed）。
    位节点命名空间取写入目标的命名空间索引（如 ns=3;s=DB1.SafetyOK）。
    client 为调用方在连接锁内取的快照，避免与并发 connect/disconnect 竞态。
    """
    ns = _node_namespace(node_id)
    if not ns or client is None:
        for addr in bit_addresses:
            _BIT_CACHE[addr] = None
        return
    for addr in bit_addresses:
        try:
            bit_node = client.get_node(f"ns={ns};s={addr}")
            raw = await bit_node.read_value()
            _BIT_CACHE[addr] = bool(raw) if raw is not None else None
        except Exception:
            _BIT_CACHE[addr] = None


async def _probe_connection(client) -> bool:
    """轻量健康探测：能读取 Objects 节点属性则认为连接存活。"""
    try:
        await client.get_node("ns=0;i=85").read_browse_name()
        return True
    except Exception:
        return False


def _parse_bool(value_str: str) -> bool:
    """解析布尔字符串；无法解析时抛 ValueError（不再静默返回 False）。"""
    text = value_str.strip().lower()
    if text in ("true", "1", "yes", "on"):
        return True
    if text in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"无法将 {value_str!r} 解析为布尔值（接受 true/false/1/0/yes/no/on/off）")


async def _vtype_for(node_id: str, node) -> object:
    """读取节点 VariantType（按节点缓存，避免每次写入重复往返）。"""
    vtype = _VTYPE_CACHE.get(node_id)
    if vtype is None:
        vtype = await node.read_data_type_as_variant_type()
        _VTYPE_CACHE[node_id] = vtype
    return vtype


def _convert_by_vtype(value_str: str, vtype) -> object:
    """按节点真实 VariantType 转换值（data_type=auto 时使用）。

    避免类型不匹配导致的序列化错误（小数串写整数节点 → struct.error、
    数字串写 String 节点 → AttributeError）；无法按类型转换时抛 ValueError。
    """
    name = getattr(vtype, "name", "")
    if name == "Boolean":
        return _parse_bool(value_str)
    if name in ("SByte", "Byte", "Int16", "UInt16", "Int32", "UInt32", "Int64", "UInt64"):
        return int(value_str)
    if name in ("Float", "Double"):
        return float(value_str)
    return value_str  # String 及其他类型按字符串写入


safety_validator.set_bit_reader(_read_safety_bit)


# ═══════════════════════════════════════
#  连接管理
# ═══════════════════════════════════════

@mcp.tool(
    name="opcua_connect",
    annotations={"destructiveHint": False},
)
async def connect(endpoint: str = "", auth_token: str = "") -> str:
    """连接到 OPC UA 服务器（西门子 PLC 默认端口 4840）

    Args:
        endpoint: 仅允许为空或唯一隔离 PLCSIM 的 OPC UA 端点
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    global _client, _endpoint, _conn_generation

    try:
        # approved_opcua_endpoint() 在控制目标配置缺失时同样抛 TargetConfigurationError，
        # 须与 require_opcua_endpoint 一起捕获，走同一友好拒绝路径，避免原始异常逃逸出工具。
        endpoint = endpoint or approved_opcua_endpoint()
        require_opcua_endpoint(endpoint)
    except TargetConfigurationError as exc:
        return f"🚫 连接被拒绝: {exc}"

    if not ASYNCUA_AVAILABLE:
        return "❌ asyncua 未安装。请运行: pip install asyncua"

    async with _conn_lock:
        if _client is not None:
            if await _probe_connection(_client):
                return f"⚠ 已连接到 {_endpoint}，请先断开"
            # 连接已失效：清理陈旧引用后允许重连（不再被幽灵连接卡死）。
            # 与 disconnect() 一致地清空位/类型缓存，避免重连后复用上一会话
            # 缓存的 VariantType 与安全位值（PLC 工程变化后可能陈旧错误）。
            try:
                await _client.disconnect()
            except Exception as exc:
                _logger.warning("清理失效连接失败: %s", exc)
            _client = None
            _endpoint = ""
            _BIT_CACHE.clear()
            _VTYPE_CACHE.clear()
            _conn_generation += 1

        client = Client(url=endpoint)
        try:
            if _SECURITY_STRING:
                await client.set_security_string(_SECURITY_STRING)
            await client.connect()
        except Exception as exc:
            _logger.warning("连接失败: %s", exc)
            return f"❌ 连接失败: {_safe_error(exc)}"
        _client = client
        _endpoint = endpoint
        _conn_generation += 1
        return f"✅ 已连接到 {endpoint}"


@mcp.tool(
    name="opcua_disconnect",
    annotations={"destructiveHint": False},
)
async def disconnect(auth_token: str = "") -> str:
    """断开 OPC UA 连接

    Args:
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "opcua")
    global _client, _endpoint, _conn_generation

    async with _conn_lock:
        if _client is None:
            return "⚠ 未连接"
        old = _endpoint
        try:
            await _client.disconnect()
        except Exception as exc:
            _logger.warning("断开连接失败: %s", exc)
            _audit_log_safe("disconnect_failed", old, operator=actor,
                            success=False, detail=str(exc))
        _client = None
        _endpoint = ""
        _BIT_CACHE.clear()
        _VTYPE_CACHE.clear()
        _conn_generation += 1
        return f"✅ 已断开 {old}"


@mcp.tool(
    name="opcua_get_status",
    annotations={"readOnlyHint": True},
)
async def get_status(auth_token: str = "") -> str:
    """获取 OPC UA 连接状态和安全信息

    Args:
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    fuse = safety.get_fuse_status()
    # 连接锁内取快照，避免与并发 connect/disconnect 竞态读到不一致状态
    async with _conn_lock:
        current_client = _client
        current_endpoint = _endpoint
    status_lines = [
        f"asyncua: {'可用' if ASYNCUA_AVAILABLE else '未安装'}",
        f"连接: {'已连接 → ' + current_endpoint if current_client else '未连接'}",
        f"安全会话: {'已配置 (OPCUA_SECURITY_STRING)' if _SECURITY_STRING else '未配置（明文传输）'}",
        f"熔断器: {'🔴 已触发 — ' + fuse['trip_reason'] if fuse['tripped'] else '🟢 正常'}",
        f"连续错误: {fuse['consecutive_errors']}/{fuse['max_errors']}",
    ]
    return "\n".join(status_lines)


# ═══════════════════════════════════════
#  读取工具
# ═══════════════════════════════════════

@mcp.tool(
    name="opcua_read",
    annotations={"readOnlyHint": True},
)
async def read_node(node_id: str, auth_token: str = "") -> str:
    """读取 OPC UA 节点的当前值

    Args:
        node_id: 节点标识符，如 "ns=3;s=DB1.MotorSpeed" 或 "ns=3;i=100"
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    # 连接锁内取快照：避免并发 disconnect 在判空后置空 _client 的 TOCTOU 竞态
    async with _conn_lock:
        if _client is None:
            return "❌ 未连接，请先调用 opcua_connect"
        client = _client

    try:
        node = client.get_node(node_id)
        dv = await node.read_data_value()  # 单次往返同时取值和类型
        return f"节点: {node_id}\n值: {dv.Value.Value}\n类型: {dv.Value.VariantType.name}"
    except Exception as exc:
        _logger.warning("读取失败 [%s]: %s", node_id, exc)
        return f"❌ 读取失败 [{node_id}]: {_safe_error(exc)}"


@mcp.tool(
    name="opcua_browse",
    annotations={"readOnlyHint": True},
)
async def browse(node_id: str = "ns=0;i=85", depth: int = 2, auth_token: str = "") -> str:
    """浏览 OPC UA 节点树结构

    Args:
        node_id: 起始节点（默认 Objects 文件夹 ns=0;i=85）
        depth: 浏览深度（默认 2 层，最大 4 层）
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    # 连接锁内取快照：避免并发 disconnect 在判空后置空 _client 的 TOCTOU 竞态
    async with _conn_lock:
        if _client is None:
            return "❌ 未连接，请先调用 opcua_connect"
        client = _client

    depth = max(0, min(depth, _MAX_BROWSE_DEPTH))
    try:
        node = client.get_node(node_id)
        lines = []
        budget = {"remaining": _MAX_BROWSE_NODES}
        await _browse_recursive(client, node, lines, depth, 0, budget)
        return "\n".join(lines) if lines else "（空节点）"
    except Exception as exc:
        _logger.warning("浏览失败 [%s]: %s", node_id, exc)
        return f"❌ 浏览失败: {_safe_error(exc)}"


async def _browse_recursive(client, node, lines: list, max_depth: int, current_depth: int, budget: dict):
    """递归浏览节点树（带深度与总节点预算防资源耗尽；批量取回子节点避免 N+1 往返）

    client 为调用方在连接锁内取的快照，避免与并发 disconnect 竞态。
    """
    if current_depth >= max_depth or budget["remaining"] <= 0:
        return
    try:
        descriptions = await node.get_children_descriptions()
        for desc in descriptions[:50]:  # 每层最多 50 个子节点
            if budget["remaining"] <= 0:
                break
            budget["remaining"] -= 1
            indent = "  " * current_depth
            lines.append(f"{indent}├─ {desc.BrowseName.Name} [{desc.NodeId}]")
            child_node = client.get_node(desc.NodeId)
            await _browse_recursive(client, child_node, lines, max_depth, current_depth + 1, budget)
    except Exception as exc:
        _logger.warning("浏览子节点失败: %s", exc)


# ═══════════════════════════════════════
#  写入工具（带安全互锁）
# ═══════════════════════════════════════

@mcp.tool(
    name="opcua_write",
    annotations={"destructiveHint": True},
)
async def write_node(
    node_id: str,
    value: str,
    data_type: str = "auto",
    operator: str = "ai-agent",
    auth_token: str = "",
    confirmation_token: str = "",
) -> str:
    """写入 OPC UA 节点值（自动检查安全互锁）

    Args:
        node_id: 节点标识符
        value: 要写入的值（字符串形式）
        data_type: 数据类型 (auto/bool/int/float/string)；auto 按节点实际类型转换
        auth_token: 认证令牌
        confirmation_token: 一次性人工确认令牌（在全部检查通过后、执行写入前消费）

    安全机制:
        - 认证令牌验证
        - 根安全链: validator → shadow_sim → audit
        - OPC UA 互锁检查（急停、安全位）
        - 数值范围检查
        - 连续异常自动熔断
    """
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "opcua")

    # 连接锁内取快照：与并发 connect/disconnect 的 TOCTOU 防护。后续全程使用
    # 局部快照 client，连接中途被替换/清除可通过代际计数 conn_generation 识别。
    async with _conn_lock:
        if _client is None:
            return "❌ 未连接，请先调用 opcua_connect"
        client = _client
        conn_generation = _conn_generation

    # 0. 类型转换（提前到所有安全链之前，让数值检查拿到真正的数值类型；转换失败 fail-closed）
    tag_name = _node_id_to_tag(node_id)
    try:
        converted = _convert_value(value, data_type)
    except (ValueError, TypeError) as exc:
        safety.record_write(node_id, value, False, str(exc), count_fuse=False)
        _audit_log_safe("write", node_id, str(value), operator=actor, success=False, detail=str(exc))
        return f"❌ 写入被拒绝: 值无法按类型 {data_type} 转换: {exc}"

    # 1. 根安全链 — validator 互锁检查
    #    （传裸标签名使 write_rules 精确匹配生效；require_bits 位先异步预读）
    required_bits = _require_bits_for(tag_name)
    if required_bits is not None:
        await _refresh_safety_bits(node_id, required_bits, client)
    val_result = safety_validator.validate(tag_name, converted)
    if not val_result.allowed:
        _audit_log_safe("write_blocked", node_id, str(value), operator=actor,
                        success=False, detail=val_result.reason)
        return f"🚫 安全校验拒绝: {val_result.reason}"
    if val_result.needs_confirmation and not confirmation_token:
        reason = f"需要人工确认: {val_result.reason}"
        _audit_log_safe("write_blocked", node_id, str(value), operator=actor,
                        success=False, detail=reason)
        return f"🚫 安全校验拒绝: {reason}"

    # 2. 根安全链 — 影子仿真
    sim_result = await shadow_sim.simulate_write(tag_name, converted)
    if not sim_result.safe:
        _audit_log_safe("shadow_rejected", node_id, str(value), operator=actor,
                        success=False, detail=sim_result.reason)
        return f"🚫 影子仿真拒绝: {sim_result.reason}"

    # 3. OPC UA 专用互锁检查（读取 PLC 安全位）
    interlock_ok, interlock_reason = await safety.check_interlock(client)
    if not interlock_ok:
        safety.record_write(node_id, value, False, interlock_reason, count_fuse=False)
        _audit_log_safe("interlock_blocked", node_id, str(value), operator=actor,
                        success=False, detail=interlock_reason)
        return f"🚫 写入被拒绝: {interlock_reason}"

    # 4. 范围检查（按规范键 ns=3;s=<裸标签> 匹配 VALUE_LIMITS：裸名或其他 ns
    #    索引变体同样命中范围限制，不静默跳过上限）
    range_ok, range_reason = safety.check_value_range(f"ns=3;s={tag_name}", converted)
    if not range_ok:
        safety.record_write(node_id, value, False, range_reason, count_fuse=False)
        _audit_log_safe("range_blocked", node_id, str(value), operator=actor,
                        success=False, detail=range_reason)
        return f"🚫 值超出范围: {range_reason}"

    # 5. 一次性人工确认令牌 — 在所有检查通过后、执行写入前消费
    #    （避免后续检查拒绝或写入失败时令牌已被作废，需重新签发）
    if val_result.needs_confirmation:
        try:
            confirmation_service.consume(
                confirmation_token,
                operator=actor,
                target=node_id,
                value=value,
                device_id=_confirmation_device_id(),
            )
        except ConfirmationError as exc:
            reason = str(exc)
            _audit_log_safe("write_blocked", node_id, str(value), operator=actor,
                            success=False, detail=reason)
            return f"🚫 安全校验拒绝: {reason}"

    # 6. 执行写入
    #    begin_control_operation 是控制动作的审计前置门（fail-closed）：审计链
    #    不可用（AuditStorageError/AuditConfigurationError）时拒绝执行写入，异常
    #    经 _safe_error 脱敏返回，不向客户端泄漏日志路径/存储细节；此处单独捕获
    #    也避免了原 try 的 except 处理器再次调用 _audit.log 二次抛错掩盖原始异常。
    try:
        _audit.begin_control_operation(
            "opcua.write_node", node_id, actor,
            {"node_id": node_id, "value": value, "data_type": data_type},
        )
    except Exception as exc:
        _logger.warning("审计前置门拒绝写入 [%s]: %s", node_id, exc)
        safety.record_write(node_id, value, False, "审计链不可用，拒绝执行写入",
                            count_fuse=False)
        _audit_log_safe("write", node_id, str(value), operator=actor, success=False,
                        detail="审计链不可用，拒绝执行写入")
        return f"🚫 写入被拒绝: 审计链不可用（{_safe_error(exc)}）"

    try:
        node = client.get_node(node_id)
        if data_type == "auto":
            vtype = await _vtype_for(node_id, node)
            converted = _convert_by_vtype(value, vtype)
            dv = ua.DataValue(ua.Variant(converted, vtype))
        else:
            dv = ua.DataValue(ua.Variant(converted))
        await node.write_value(dv)

        # 7. 读回验证
        readback = await node.read_value()
        safety.record_write(node_id, value, True)
        _audit_log_safe("write", node_id, str(value), operator=actor, success=True)
        return f"✅ 已写入 {node_id} = {readback}"
    except Exception as exc:
        # 连接在操作期间被并发 connect/disconnect 替换/清除时，失败属于连接
        # 生命周期变更而非真实写入失败，不计入熔断计数（避免无谓熔断锁死全部写入）。
        conn_replaced = conn_generation != _conn_generation
        safety.record_write(node_id, value, False, str(exc), count_fuse=not conn_replaced)
        _audit_log_safe("write", node_id, str(value), operator=actor, success=False, detail=str(exc))
        return f"❌ 写入失败: {_safe_error(exc)}"


@mcp.tool(
    name="opcua_reset_fuse",
    annotations={"destructiveHint": True},
)
async def reset_fuse(auth_token: str = "", confirmation_token: str = "") -> str:
    """重置安全熔断器（连续写入失败后自动触发熔断，需人工重置）

    Args:
        auth_token: 认证令牌
        confirmation_token: 一次性人工确认令牌（必须为 fuse_reset 用途签发）

    安全机制:
        熔断的意义在于异常后强制人工介入。没有人工确认令牌就能远程重置，
        熔断机制就形同虚设，因此必须消费一次性令牌后才允许重置。
    """
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "opcua")

    # 先核实熔断状态再消费令牌：熔断未触发时返回"无需重置"，不得作废一次性
    # 确认令牌。opcua_safety 与根安全链 validator 各自维护熔断计数，任一熔断
    # 即视为需要重置（validator 阈值与其实例加载的配置一致）。
    fuse = safety.get_fuse_status()
    validator_fuse_tripped = getattr(safety_validator, "consecutive_errors", 0) >= getattr(
        _validator_module, "_MAX_ERRORS", 3
    )
    if not fuse["tripped"] and not validator_fuse_tripped:
        reason = "熔断器未触发，无需重置"
        _audit_log_safe("fuse_reset_blocked", "opcua.fuse_reset", "", operator=actor,
                        success=False, detail=reason)
        return f"⚠ {reason}"

    if not confirmation_token:
        reason = "重置熔断器需要一次性人工确认令牌"
        _audit_log_safe("fuse_reset_blocked", "opcua.fuse_reset", "", operator=actor,
                        success=False, detail=reason)
        return f"🚫 {reason}"
    try:
        confirmation_service.consume(
            confirmation_token,
            operator=actor,
            target="opcua.fuse_reset",
            value="reset",
            device_id=_confirmation_device_id(),
        )
    except ConfirmationError as exc:
        _audit_log_safe("fuse_reset_blocked", "opcua.fuse_reset", "", operator=actor,
                        success=False, detail=str(exc))
        return f"🚫 熔断器重置被拒绝: {exc}"
    result = safety.reset_fuse()
    safety_validator.reset_fuse()  # 同步重置根安全链熔断计数（同样需已消费人工确认令牌）
    _audit_log_safe("fuse_reset", "opcua.fuse_reset", "reset", operator=actor)
    return result


# ═══════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════

def _convert_value(value_str: str, data_type: str):
    """将字符串值转换为目标类型（int/float/bool 失败时抛 ValueError，由调用方 fail-closed 处理）"""
    if data_type == "bool":
        return _parse_bool(value_str)
    elif data_type == "int":
        return int(value_str)
    elif data_type == "float":
        return float(value_str)
    elif data_type == "string":
        return value_str
    else:  # auto — 先按字符串文本推断用于安全链数值检查；写入前再按节点 VariantType 转换
        if value_str.strip().lower() in ("true", "false"):
            return value_str.strip().lower() == "true"
        try:
            return int(value_str)
        except ValueError:
            pass
        try:
            return float(value_str)
        except ValueError:
            pass
        return value_str


# ═══════════════════════════════════════
#  入口
# ═══════════════════════════════════════

if __name__ == "__main__":
    if "--test" in sys.argv:
        print("OPC UA MCP Server — 测试模式")
        print(f"asyncua: {'可用' if ASYNCUA_AVAILABLE else '未安装 (pip install asyncua)'}")
        print(f"安全模块: 已加载")
        print(f"熔断器: {safety.get_fuse_status()}")
    else:
        mcp.run(transport="stdio")
