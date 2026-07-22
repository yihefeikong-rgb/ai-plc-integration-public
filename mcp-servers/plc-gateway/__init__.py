"""PLC Engineering Gateway — 入口点"""
from __future__ import annotations

from .registry import get_registry, register_default_tools
from .providers import TiaWorkerProvider
from .policy import configure_default_routing

# 注册默认工具
register_default_tools()

__all__ = ["get_registry", "configure_default_routing", "TiaWorkerProvider"]