"""
PLC Engineering Gateway — 引导模块

组装所有组件（Provider、安全链、路由策略、注册表），
返回完整的 GatewayContext 供 server.py 使用。

启动顺序：
  1. 加载配置
  2. 初始化 Provider
  3. 初始化安全链
  4. 初始化路由策略
  5. 注册工具
  6. 返回 GatewayContext
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from plc_gateway.config import GatewayConfig
from plc_gateway.providers.base import TiaProvider, ProviderResult
from plc_gateway.providers.tiaworker import TiaWorkerProvider
from mcp_common.tiaworker_client import TiaWorkerClient
from plc_gateway.providers.tiacommander import create_provider as create_tiacommander
from plc_gateway.registry import get_registry, register_default_tools, ToolCategory
from plc_gateway.policy.routing import RoutingPolicy, configure_default_routing
from plc_gateway.contracts.safety_chain import SafetyChain, get_safety_chain
from plc_gateway.contracts.preview_apply import get_preview_manager

_logger = logging.getLogger(__name__)


class GatewayContext:
    """Gateway 运行上下文 — 持有所有运行时组件"""

    def __init__(self, config: GatewayConfig):
        self.config = config
        self.registry = get_registry()
        self.routing: RoutingPolicy | None = None
        self.safety: SafetyChain | None = None
        self.providers: dict[str, TiaProvider] = {}
        self.gateway_id: str = uuid.uuid4().hex[:8]

    def to_dict(self) -> dict:
        return {
            "gateway_id": self.gateway_id,
            "config": self.config.to_dict(),
            "providers": {
                name: {
                    "available": p.available,
                    "name": p.name,
                }
                for name, p in self.providers.items()
            },
            "tools_count": len(self.registry),
            "safety_enabled": self.config.safety_enabled,
        }

    def get_provider_info(self) -> list[dict]:
        """获取所有 Provider 的状态信息"""
        result = []
        for name, provider in self.providers.items():
            result.append({
                "name": name,
                "configured": True,
                "available": provider.available,
                "read_enabled": True,
                "write_enabled": False,
            })
        return result

    def list_capabilities(self) -> dict:
        """只声明 FastMCP 实际暴露且当前 Provider 可执行的能力。"""
        exposed = [
            "gateway.get_info", "gateway.list_providers", "gateway.list_capabilities",
            "tia.project.info", "tia.project.list", "tia.block.list",
            "tia.block.get_interface", "tia.block.get_xml", "tia.hardware.list",
        ]
        provider = self.routing.get_read_provider() if self.routing else None
        available = exposed[:3]
        unavailable = {}
        if provider and provider.available:
            available.extend(name for name in exposed[3:] if name != "tia.block.get_xml")
            unavailable["tia.block.get_xml"] = "TiaWorker XML 导出协议尚未验证"
        else:
            unavailable = {name: "没有可用的只读 Provider" for name in exposed[3:]}
        return {
            "declared_count": len(exposed),
            "exposed": exposed,
            "available": available,
            "unavailable": unavailable,
        }


def _find_tiaworker_exe(config: GatewayConfig) -> str:
    """查找 TiaWorker.exe 路径"""
    if config.tiaworker_exe:
        exe = Path(config.tiaworker_exe)
        if exe.exists():
            return str(exe)
        _logger.warning(f"配置的 TiaWorker 路径不存在: {exe}")

    candidates = [
        Path(__file__).parent.parent / "tia-mcp" / "bin" / "TiaWorker.exe",
        Path(__file__).parent.parent.parent / "mcp-servers" / "tia-mcp" / "bin" / "TiaWorker.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    _logger.warning("未找到 TiaWorker.exe")
    return ""


def _init_providers(ctx: GatewayContext) -> dict[str, TiaProvider]:
    """初始化所有 Provider"""
    providers: dict[str, TiaProvider] = {}

    if ctx.config.default_read_provider == "tiacommander":
        raise RuntimeError("TiaCommander 尚未实现实际项目身份校验，不能作为默认只读 Provider")

    tiaworker_exe = _find_tiaworker_exe(ctx.config)
    if tiaworker_exe:
        client = TiaWorkerClient(tiaworker_exe, tia_version=ctx.config.tia_version)
        providers["tiaworker"] = TiaWorkerProvider(
            client, project_path=ctx.config.target_project)
        _logger.info(f"TiaWorker 已初始化")
    else:
        providers["tiaworker"] = _UnavailableProvider("tiaworker")
        _logger.warning("TiaWorker 不可用")

    if ctx.config.tiacommander_enabled:
        provider = create_tiacommander(ctx.config.tiacommander_dir)
        if provider:
            providers["tiacommander"] = provider
            _logger.info("TiaCommander 已初始化")
        else:
            providers["tiacommander"] = _UnavailableProvider("tiacommander")
            _logger.warning("TiaCommander 不可用")

    return providers


def _init_safety(ctx: GatewayContext) -> SafetyChain:
    """初始化安全链"""
    secret_key = ctx.config.secret_key or os.urandom(32).hex()
    if not ctx.config.secret_key:
        _logger.warning("secret_key 未配置，使用随机密钥（重启后失效）")
    chain = SafetyChain(config={
        "secret_key": secret_key,
        "preview_ttl": ctx.config.preview_ttl,
    })
    mgr = get_preview_manager()
    mgr.set_ttl(ctx.config.preview_ttl)
    mgr.set_secret_key(secret_key)
    chain.set_preview_manager(mgr)
    return chain


def _init_routing(ctx: GatewayContext) -> RoutingPolicy:
    """初始化路由策略"""
    policy = RoutingPolicy(
        default_read=ctx.config.default_read_provider,
        default_write=ctx.config.default_write_provider,
    )
    for name, provider in ctx.providers.items():
        policy.register_provider(provider)
    return policy


class _UnavailableProvider(TiaProvider):
    """不可用的 Provider 占位"""

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self) -> bool:
        return False

    @property
    def read_only(self) -> bool:
        return True

    def _err(self, operation: str) -> ProviderResult:
        return ProviderResult.error_result(operation, f"{self._name} 不可用", provider=self._name, status="unavailable")

    def get_project_info(self) -> ProviderResult:
        return self._err(f"{self._name}.project.info")

    def list_blocks(self) -> ProviderResult:
        return self._err(f"{self._name}.block.list")

    def get_block_xml(self, block_name: str) -> ProviderResult:
        return self._err(f"{self._name}.block.get_xml")

    def get_block_interface(self, block_name: str) -> ProviderResult:
        return self._err(f"{self._name}.block.get_interface")

    def compile_project(self) -> ProviderResult:
        return self._err(f"{self._name}.project.compile")

    def list_devices(self) -> ProviderResult:
        return self._err(f"{self._name}.hardware.list")

    def apply_patch(self, patch: dict) -> ProviderResult:
        return self._err(f"{self._name}.apply_patch")

    def preview_patch(self, patch: dict) -> ProviderResult:
        return self._err(f"{self._name}.preview_patch")


def bootstrap_gateway(config: GatewayConfig | None = None) -> GatewayContext:
    """引导 Gateway — 组装所有组件

    Args:
        config: 配置，为 None 时从环境变量加载

    Returns:
        装配完成的 GatewayContext
    """
    if config is None:
        config = GatewayConfig.from_env()

    logging.basicConfig(
        level=logging.DEBUG if config.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    _logger.info("正在引导 PLC Engineering Gateway...")
    ctx = GatewayContext(config)

    # 1. 注册默认工具元数据
    register_default_tools()
    _logger.info(f"已注册 {len(ctx.registry)} 个工具")

    # 2. 初始化 Provider
    ctx.providers = _init_providers(ctx)
    _logger.info(f"Provider: {list(ctx.providers.keys())}")

    # 3. 初始化安全链
    if config.safety_enabled:
        ctx.safety = _init_safety(ctx)
        _logger.info("安全链已启用")
    else:
        _logger.warning("安全链已禁用！")

    # 4. 初始化路由
    ctx.routing = _init_routing(ctx)
    _logger.info(f"路由已配置")

    # 5. 注册系统工具
    _register_system_tools(ctx)

    _logger.info(f"Gateway 引导完成 (id={ctx.gateway_id})")
    return ctx


def _register_system_tools(ctx: GatewayContext) -> None:
    """注册系统工具到注册表（幂等，跳过已注册项）"""
    from plc_gateway.registry import register_tool, ToolMetadata, RiskLevel

    _system_tools = [
        ToolMetadata(
            name="gateway.get_info",
            risk_level=RiskLevel.L0_READ_ONLY,
            read_only=True,
            description="获取 Gateway 自身信息（ID、配置、Provider 状态、工具数量）",
            category=ToolCategory.SYSTEM,
        ),
        ToolMetadata(
            name="gateway.list_providers",
            risk_level=RiskLevel.L0_READ_ONLY,
            read_only=True,
            description="列出所有已配置的 Provider 及其状态",
            category=ToolCategory.SYSTEM,
        ),
        ToolMetadata(
            name="gateway.list_capabilities",
            risk_level=RiskLevel.L0_READ_ONLY,
            read_only=True,
            description="列出 Gateway 支持的所有工具名称",
            category=ToolCategory.SYSTEM,
        ),
    ]
    for meta in _system_tools:
        try:
            register_tool(meta)
        except ValueError:
            pass  # 已注册则跳过
