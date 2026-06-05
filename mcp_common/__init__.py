"""
mcp_common — 公共库，所有 MCP Server 共享的基础设施。

统一了原来分散在 safety/、tia-mcp/、config/ 中的重复逻辑：
  - audit:    统一审计日志（链式哈希 + JSON Lines）
  - config:   统一配置加载（YAML + .env + ${ENV:default}）
  - deepseek: DeepSeek API 调用封装
  - connection: 惰性单例连接管理器
"""

from mcp_common.audit import AuditLogger, get_audit_logger
from mcp_common.config import Config, load_yaml_config, env_config
from mcp_common.deepseek import call_deepseek, parse_json_response
from mcp_common.connection import ConnectionManager

__all__ = [
    "AuditLogger", "get_audit_logger",
    "Config", "load_yaml_config", "env_config",
    "call_deepseek", "parse_json_response",
    "ConnectionManager",
]
