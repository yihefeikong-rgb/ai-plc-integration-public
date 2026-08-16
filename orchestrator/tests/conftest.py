"""orchestrator 测试隔离配置 — 审计日志重定向到临时目录。

orchestrator/tests 会实例化真实 SafetyGate 并触发审计写入；不重定向时
这些写入会落到仓库 logs/audit.log（真实审计链），污染历史记录。本 conftest
把 mcp_common.audit 单例及 safety.audit 兼容层的所有绑定统一重定向到每个
测试独立的 tmp_path，确保整个 orchestrator/tests 不触碰 logs/audit.log。

重定向点（覆盖全部审计入口）:
  - mcp_common.audit._audit_logger — get_audit_logger() 与 audit 惰性代理
    共享的全局单例；core.py 的 _audit_control_intent / _audit_tool_call
    按调用时 `from mcp_common.audit import get_audit_logger` 取值，同样
    读该全局
  - safety.audit._audit_logger / safety.audit.audit — 兼容层 import 时
    立即创建的模块级单例
  - orchestrator.safety_gate.audit — `from safety.audit import audit` 的
    模块级绑定（SafetyGate.check_write 直接使用）
"""
import pytest

import mcp_common.audit as _mcp_audit
import orchestrator.safety_gate as _orch_gate
import safety.audit as _safety_audit
from mcp_common.audit import AuditLogger


@pytest.fixture(autouse=True)
def _isolated_audit_log(tmp_path):
    """每个测试的审计写入重定向到 tmp_path，测试结束后恢复原绑定。"""
    test_logger = AuditLogger(
        tmp_path / "audit.log",
        hmac_key="orchestrator-tests-audit-key",
        production=False,
    )

    saved = (
        _mcp_audit._audit_logger,
        _safety_audit._audit_logger,
        _safety_audit.audit,
        _orch_gate.audit,
    )
    _mcp_audit._audit_logger = test_logger
    _safety_audit._audit_logger = test_logger
    _safety_audit.audit = test_logger
    _orch_gate.audit = test_logger

    yield test_logger

    (
        _mcp_audit._audit_logger,
        _safety_audit._audit_logger,
        _safety_audit.audit,
        _orch_gate.audit,
    ) = saved
