"""
审计日志 — 兼容层，从 mcp_common.audit 重新导出。

所有审计功能已统一到 mcp_common/audit.py：
  - AuditLogger 类（链式哈希防篡改）
  - get_audit_logger() 单例工厂
  - audit_log() 便捷函数

用法（向后兼容）:
    from safety.audit import audit
    audit.log("write", "DB1.Motor", "1500", operator="ai")
"""

from mcp_common.audit import AuditLogger, get_audit_logger, audit_log

# 全局单例（兼容现有代码: from safety.audit import audit）
_audit_logger: AuditLogger = get_audit_logger()
audit = _audit_logger

__all__ = [
    "AuditLogger",
    "get_audit_logger",
    "audit_log",
    "audit",
]
