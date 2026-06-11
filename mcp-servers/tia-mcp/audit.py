"""
审计日志 — 兼容层，从 mcp_common.audit 重新导出。

所有审计功能已统一到 mcp_common/audit.py：
  - AuditLogger 类（链式哈希防篡改）
  - get_audit_logger() 单例工厂
  - audit_log() 便捷函数 read_logs() 读取函数

用法（向后兼容）:
    from audit import audit_log
    audit_log("create_ladder_block", user_input="电机正反转", block_name="MotorFwdRev", result="ok")
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中（使 mcp_common 可导入）
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp_common.audit import AuditLogger, get_audit_logger, audit_log, read_logs

__all__ = [
    "AuditLogger",
    "get_audit_logger",
    "audit_log",
    "read_logs",
]
