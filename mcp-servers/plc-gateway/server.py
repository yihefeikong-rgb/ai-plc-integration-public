"""
PLC Engineering Gateway — FastMCP Server

将 Gateway 以 MCP stdio 协议暴露给 AI 客户端（Claude Code 等）。
所有工具通过 bootstrap.py 装配的 GatewayContext 和 registry 管理。

启动方式:
  python server.py

环境变量配置:
  目标项目与 TIA 版本均来自 mcp-servers/tia-mcp/config.yaml 的 target 节
  GATEWAY_TIACOMMANDER_DIR  - TiaCommander 目录（可选）
  GATEWAY_TIACOMMANDER_ENABLED=1 - 启用 TiaCommander
  GATEWAY_SAFETY_ENABLED=0  - 禁用安全链
  GATEWAY_DEBUG=1           - 调试日志
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# 直接执行 ``server.py`` 时仍支持旧入口；标准入口是
# ``python -m plc_gateway.server``，它不依赖目录顺序。
if __package__ in (None, ""):
    _PROJECT_ROOT = Path(__file__).resolve().parents[2]
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))

from fastmcp import FastMCP

from plc_gateway.bootstrap import bootstrap_gateway, GatewayContext
from plc_gateway.registry import ToolCategory, RiskLevel, get_registry

_logger = logging.getLogger(__name__)

# ── 全局 Gateway 上下文 ──
_context: GatewayContext | None = None


def get_context() -> GatewayContext:
    """获取全局 Gateway 上下文"""
    global _context
    if _context is None:
        _context = bootstrap_gateway()
    return _context


def _get_read_provider() -> tuple[Any, dict | None]:
    """获取只读 Provider，经过安全链检查

    Returns:
        (provider, None) 成功
        (None, error_dict) 失败
    """
    ctx = get_context()
    provider = ctx.routing.get_read_provider() if ctx.routing else None
    if not provider or not provider.available:
        return None, {"ok": False, "error": "没有可用的只读 Provider"}

    if not ctx.config.target_project:
        return None, {"ok": False, "status": "blocked", "error": {"code": "TARGET_NOT_CONFIGURED", "message": "未配置唯一受控项目目标"}}

    # Provider 只能携带由统一配置注入的项目路径；空路径或漂移均失败关闭。
    if ctx.safety:
        result = ctx.safety.check_target(getattr(provider, "project_path", ""), ctx.config.target_project)
        if not result.allowed:
            return None, {"ok": False, "status": "blocked", "error": {"code": "TARGET_MISMATCH", "message": result.reason}}

    return provider, None


# ── 创建 MCP 服务器 ──
mcp = FastMCP("PLC Engineering Gateway")


# ── 系统工具 ──


@mcp.tool(name="gateway.get_info", description="获取 Gateway 自身信息")
def gateway_get_info() -> dict:
    """获取 Gateway 运行时信息"""
    return get_context().to_dict()


@mcp.tool(name="gateway.list_providers", description="列出所有已配置的 Provider 及其状态")
def gateway_list_providers() -> list[dict]:
    """列出所有 Provider 的状态"""
    return get_context().get_provider_info()


@mcp.tool(name="gateway.list_capabilities", description="列出 Gateway 支持的所有工具名称")
def gateway_list_capabilities() -> list[str]:
    """列出所有可用工具"""
    return get_context().list_capabilities()


# ── TIA 项目工具 ──


@mcp.tool(name="tia.project.info", description="获取当前 TIA 项目信息")
def tia_project_info() -> dict:
    """获取项目信息"""
    provider, err = _get_read_provider()
    if err:
        return err
    return provider.get_project_info().to_dict()


@mcp.tool(name="tia.project.list", description="列出 TIA 项目中的块（同 tia.block.list）")
def tia_project_list() -> dict:
    """列出所有块"""
    provider, err = _get_read_provider()
    if err:
        return err
    return provider.list_blocks().to_dict()


# ── 块工具 ──


@mcp.tool(name="tia.block.list", description="列出项目中的所有 PLC 块")
def tia_block_list() -> dict:
    """列出所有块"""
    provider, err = _get_read_provider()
    if err:
        return err
    return provider.list_blocks().to_dict()


@mcp.tool(name="tia.block.get_interface", description="读取 PLC 块的接口信息")
def tia_block_get_interface(block_name: str) -> dict:
    """获取块接口"""
    provider, err = _get_read_provider()
    if err:
        return err
    return provider.get_block_interface(block_name).to_dict()


@mcp.tool(name="tia.block.get_xml", description="读取 PLC 块的原始 SimaticML XML")
def tia_block_get_xml(block_name: str) -> dict:
    """获取块 XML"""
    provider, err = _get_read_provider()
    if err:
        return err
    return provider.get_block_xml(block_name).to_dict()


# ── 硬件工具 ──


@mcp.tool(name="tia.hardware.list", description="列出项目中的硬件设备")
def tia_hardware_list() -> dict:
    """列出设备"""
    provider, err = _get_read_provider()
    if err:
        return err
    return provider.list_devices().to_dict()


# ── 入口 ──


def main() -> None:
    """启动 Gateway MCP 服务器"""
    ctx = get_context()
    _logger.info(f"PLC Engineering Gateway 启动 (id={ctx.gateway_id})")
    _logger.info(f"  已注册工具: {len(ctx.registry)} 个")
    _logger.info(f"  Provider: {list(ctx.providers.keys())}")
    tia_avail = ctx.providers.get("tiaworker", None) and ctx.providers["tiaworker"].available
    _logger.info(f"  TiaWorker 可用: {tia_avail}")
    _logger.info(f"  传输方式: stdio")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
