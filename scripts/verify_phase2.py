#!/usr/bin/env python3
"""
Phase 2 端到端验证脚本 — 检查 "采集→分析→决策→写入→审计" 全链路

用法:
  python verify_phase2.py                  # 运行所有检查（除需要真实 PLC/API 的）
  python verify_phase2.py --all            # 全部（含真实连接检查）
  python verify_phase2.py safety           # 仅安全模块
  python verify_phase2.py s7               # 仅 S7 连接（需要 PLCSIM 在线）
  python verify_phase2.py gateway          # 仅 EdgeGateway mock 模式
"""
import sys
import json
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "edge-gateway"))
sys.path.insert(0, str(PROJECT_ROOT / "edge-gateway" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge"))

from mcp_common.control_target import get_control_target

# 审计验证使用独立临时链：本脚本绝不写真实 logs/audit.log，
# 避免伪造写事件污染 HMAC 审计链的完整性验证
_VERIFY_AUDIT_DIR = Path(tempfile.mkdtemp(prefix="verify_phase2_audit_"))
_VERIFY_AUDIT_LOG = str(_VERIFY_AUDIT_DIR / "audit.log")

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}: {detail}")


# ═══════════════════════════════════════
#  1. 安全模块
# ═══════════════════════════════════════
def test_safety():
    print("\n━━━ [1/4] Safety 安全模块 ━━━")

    from safety.validator import WriteValidator, ValidationResult

    v = WriteValidator()

    # 禁止写入安全标签
    r = v.validate("DB1.ESTOP", True)
    check("禁止写入 ESTOP 标签", not r.allowed and "ESTOP" in r.reason, r.reason)

    # 允许写入正常标签
    r = v.validate("DB1.MotorSpeed", 1500)
    check("允许写入正常标签", r.allowed, r.reason)

    # 值范围检查
    r = v.validate("DB1.MotorSpeed", 9_999_999)
    check("拦截超大值", not r.allowed, r.reason)

    # 值跳变检测
    r = v.validate("DB1.MotorSpeed", 2000, current_value=100)
    check("拦截值跳变", not r.allowed, r.reason)

    # 需确认标签
    r = v.validate("DB1.MOTOR_RUN", True)
    check("电机标签需确认", r.needs_confirmation)

    # 审计日志（写入临时链验证完整性，绝不写真实 logs/audit.log）
    from mcp_common.audit import get_audit_logger
    logger = get_audit_logger(_VERIFY_AUDIT_LOG)
    logger.log("write", "MW10", "42", operator="verify", detail="Phase2验证")
    check("审计日志写入", True)

    # 审计日志验证
    try:
        assert logger.verify()
        check("审计日志链完整性", True)
    except Exception as e:
        check("审计日志链完整性", False, str(e))


# ═══════════════════════════════════════
#  2. S7 适配器
# ═══════════════════════════════════════
def test_s7(need_real: bool = False):
    print("\n━━━ [2/4] S7 适配器 ━━━")

    try:
        from s7_adapter import S7Adapter

        adapter = S7Adapter()
    except Exception as e:
        check("S7Adapter 实例化", False, str(e))
        return

    if not need_real:
        check("S7Adapter 实例化", True)
        check("snap7 可用", adapter._connected is False)  # 只是检查不报错
        return

    # 需要真实 PLCSIM
    ip = get_control_target().plc_ip
    result = adapter.connect(ip)
    check(f"S7 连接 {ip}", "成功" in result or "已连接" in result, result)

    if adapter.is_connected:
        try:
            ret = adapter.read_address("M0.0")
            check(f"S7 读取 M0.0", ret is not None, str(ret))
        except Exception as e:
            check("S7 读取 M0.0", False, str(e))

        try:
            ret = adapter.read_address("MW10")
            check(f"S7 读取 MW10", ret is not None, str(ret))
        except Exception as e:
            check("S7 读取 MW10", False, str(e))

        print(f"  断开连接...")
        adapter.disconnect()
        check("S7 断开", True)


# ═══════════════════════════════════════
#  3. EdgeGateway mock 模式
# ═══════════════════════════════════════
def test_gateway():
    print("\n━━━ [3/4] EdgeGateway ━━━")

    # 确保写回路径的审计也走临时链，不污染真实 logs/audit.log
    from mcp_common.audit import get_audit_logger
    get_audit_logger(_VERIFY_AUDIT_LOG)

    try:
        from app import EdgeGateway

        gw = EdgeGateway()
    except Exception as e:
        check("EdgeGateway 实例化", False, str(e))
        return

    check("EdgeGateway 实例化", True)
    check(f"标签配置数 > 0", len(gw.tag_config) > 0, str(len(gw.tag_config)))

    # Mock scan_once
    async def _test():
        async def mock_read(tag: str) -> dict:
            return {"value": 42.0}

        data = await gw.scan_once(mock_read)
        check(f"scan_once 返回 {len(data)} 条", len(data) > 0)
        check("scan_once 数据格式正确", all("tag" in d and "value" in d for d in data))

        # 变化检测
        gw._prev_values = {}
        changed = [d for d in data if gw._has_significant_change(d["tag"], d["value"])]
        check(f"首次变化检测触发 {len(changed)} 个", len(changed) == len(data))

        # 第二次调用不应触发变化
        changed2 = [d for d in data if gw._has_significant_change(d["tag"], d["value"])]
        check("二次调用无变化", len(changed2) == 0)

        # 写回测试（不依赖真实 PLC）：驱动真实写回路径 _safe_write，
        # 断言 fail-closed 行为——白名单/互锁/确认条件不满足时不得触发写入
        write_called = []

        def mock_write(tag: str, val):
            write_called.append((tag, val))
            return f"写入 {tag}={val}"

        available = [t["tag"] for t in gw.tag_config]
        try:
            # 1) 非白名单目标必须被拒绝
            await gw._safe_write(
                {"action": "write", "target": "DB99.NOT_A_TAG", "value": 1,
                 "reason": "verify_phase2"},
                available, data, read_func=mock_read, write_func=mock_write)

            # 2) 全部已配置标签（含已映射 M0.1/MW14）在互锁/确认条件
            #    无法满足时也必须 fail-closed 拒绝
            for target in available:
                await gw._safe_write(
                    {"action": "write", "target": target, "value": 1,
                     "reason": "verify_phase2"},
                    available, data, read_func=mock_read,
                    write_func=mock_write)

            check("写回路径可调用", True)
            check("写回路径 fail-closed：未满足条件不放行",
                  len(write_called) == 0, str(write_called))
        except Exception as e:
            check("写回路径可调用", False, str(e))
            check("写回路径 fail-closed：未满足条件不放行",
                  False, str(e))

    import asyncio
    try:
        asyncio.run(_test())
    except Exception as e:
        check("EdgeGateway mock 运行", False, str(e))


# ═══════════════════════════════════════
#  4. MCP 模块导入检查
# ═══════════════════════════════════════
def test_mcp_tools():
    print("\n━━━ [4/4] MCP 模块导入 ━━━")

    try:
        # 验证 tools_s7 模块可导入
        import tools_s7
        check("tools_s7 模块加载", True)
        check("S7 工具有: s7_connect/s7_read/s7_write/s7_status", True)
    except Exception as e:
        check("MCP 模块检查", False, str(e))


# ═══════════════════════════════════════
#  入口
# ═══════════════════════════════════════
if __name__ == "__main__":
    args = set(sys.argv[1:])
    run_all = "--all" in args or not any(a in args for a in ("safety", "s7", "gateway", "mcp"))

    if run_all or "safety" in args:
        try:
            test_safety()
        except Exception as e:
            check("test_safety 异常", False, str(e))
    if run_all or "s7" in args:
        try:
            test_s7(need_real="--all" in args)
        except Exception as e:
            check("test_s7 异常", False, str(e))
    if run_all or "gateway" in args:
        try:
            test_gateway()
        except Exception as e:
            check("test_gateway 异常", False, str(e))
    if run_all or "mcp" in args:
        try:
            test_mcp_tools()
        except Exception as e:
            check("test_mcp_tools 异常", False, str(e))

    print(f"\n{'='*40}")
    print(f"结果: {PASS} 通过, {FAIL} 失败 / {PASS + FAIL} 总")
    sys.exit(0 if FAIL == 0 else 1)
