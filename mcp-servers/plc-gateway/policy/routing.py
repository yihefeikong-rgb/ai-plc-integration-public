"""Provider 路由策略 — 根据工具和风险等级选择后端提供者"""
from __future__ import annotations

from typing import Any

from providers.base import ProviderResult, TiaProvider
from policy.risk_levels import RiskLevel, is_default_disabled


class RoutingPolicy:
    """路由策略 — 决定哪个 Provider 处理哪个工具"""

    def __init__(self, default_read: str = "tiaworker",
                 default_write: str = "tiaworker"):
        self._providers: dict[str, TiaProvider] = {}
        self._default_read = default_read
        self._default_write = default_write

    def register_provider(self, provider: TiaProvider) -> None:
        self._providers[provider.name] = provider

    def get_provider(self, name: str) -> TiaProvider | None:
        return self._providers.get(name)

    def get_read_provider(self) -> TiaProvider | None:
        """获取默认只读提供者"""
        return self._providers.get(self._default_read)

    def get_write_provider(self) -> TiaProvider | None:
        """获取默认写入提供者"""
        return self._providers.get(self._default_write)

    def route(self, tool_name: str, risk_level: RiskLevel,
              preferred_provider: str | None = None) -> TiaProvider | None:
        """根据工具和风险等级路由到合适的 Provider

        Args:
            tool_name: 工具名称
            risk_level: 风险等级
            preferred_provider: 调用方偏好的提供者（可选）

        Returns:
            可用的 Provider，或 None（无可用提供者）
        """
        # 高风险的设备操作默认禁用
        if is_default_disabled(risk_level):
            return None

        # 优先使用调用方指定的提供者
        if preferred_provider and preferred_provider in self._providers:
            if self._providers[preferred_provider].available:
                return self._providers[preferred_provider]

        # 根据读写类型选择默认提供者
        if risk_level in (RiskLevel.L0_READ_ONLY, RiskLevel.L1_FILE_GEN):
            provider = self._providers.get(self._default_read)
        else:
            provider = self._providers.get(self._default_write)

        if provider and provider.available:
            return provider
        return None

    def available_providers(self) -> list[str]:
        return [name for name, p in self._providers.items() if p.available]


# ── 全局路由策略实例 ──
_policy = RoutingPolicy()


def get_policy() -> RoutingPolicy:
    return _policy


def configure_default_routing(tiaworker_provider: TiaProvider | None = None) -> RoutingPolicy:
    """配置默认路由（TiaWorker 为唯一提供者）"""
    if tiaworker_provider:
        _policy.register_provider(tiaworker_provider)
    return _policy