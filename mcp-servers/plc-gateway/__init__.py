"""PLC Engineering Gateway — 入口点"""
from __future__ import annotations

from plc_gateway.registry import get_registry, register_default_tools
from plc_gateway.providers import TiaWorkerProvider
from plc_gateway.policy import configure_default_routing

# 注册默认工具
register_default_tools()

__all__ = ["get_registry", "configure_default_routing", "TiaWorkerProvider"]
