"""
PLC Engineering Gateway — 运行时配置

定义 GatewayConfig 数据类，从环境变量和配置文件加载运行时参数。
所有配置项有合理的默认值，支持通过环境变量覆盖。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp_common.config import load_yaml_config


@dataclass
class GatewayConfig:
    """Gateway 运行时配置"""

    # ── 项目目标 ──
    target_project: str = ""
    """目标 TIA 项目路径（绝对路径），安全链依赖此值进行目标检查"""

    tia_version: str = "V21"
    """TIA Portal 版本号"""

    target_profile: str = ""
    """唯一受控目标配置的 profile 名称"""

    # ── Provider 配置 ──
    tiaworker_exe: str = ""
    """TiaWorker.exe 路径，为空时自动查找"""

    tiacommander_dir: str = ""
    """TiaCommander 目录路径，为空表示不启用"""

    tiacommander_enabled: bool = False
    """是否启用 TiaCommander Provider（默认关闭）"""

    default_read_provider: str = "tiaworker"
    """默认只读 Provider 名称"""

    default_write_provider: str = "tiaworker"
    """默认写入 Provider 名称"""

    # ── 安全配置 ──
    safety_enabled: bool = True
    """是否启用安全链"""

    secret_key: str = ""
    """HMAC 签名密钥（为空时自动生成随机密钥）"""

    preview_ttl: int = 300
    """Preview Token 有效期（秒）"""

    # ── 服务器配置 ──
    debug: bool = False
    """是否开启调试日志"""

    # ── 熔断配置 ──
    max_write_retries: int = 3
    """写操作最大重试次数"""

    write_timeout: int = 180
    """写操作超时时间（秒）"""

    reconcile_timeout: int = 30
    """Reconcile 超时时间（秒）"""

    @classmethod
    def from_env(cls) -> GatewayConfig:
        """从唯一受控目标加载配置；环境变量只覆盖 YAML 已允许的字段。"""
        target = load_yaml_config("mcp-servers/tia-mcp/config.yaml").target
        if str(target.tia_version).upper() != "V21":
            raise ValueError("PLC Gateway 仅接受唯一受控目标中的 TIA V21 配置")
        return cls(
            target_project=target.project_path,
            tia_version=target.tia_version,
            target_profile=target.profile,
            tiaworker_exe=os.environ.get("GATEWAY_TIAWORKER_EXE", ""),
            tiacommander_dir=os.environ.get("GATEWAY_TIACOMMANDER_DIR", ""),
            tiacommander_enabled=os.environ.get("GATEWAY_TIACOMMANDER_ENABLED", "0") == "1",
            default_read_provider=os.environ.get("GATEWAY_READ_PROVIDER", "tiaworker"),
            default_write_provider=os.environ.get("GATEWAY_WRITE_PROVIDER", "tiaworker"),
            safety_enabled=os.environ.get("GATEWAY_SAFETY_ENABLED", "1") == "1",
            secret_key=os.environ.get("GATEWAY_SECRET_KEY", ""),
            preview_ttl=int(os.environ.get("GATEWAY_PREVIEW_TTL", "300")),
            debug=os.environ.get("GATEWAY_DEBUG", "0") == "1",
            max_write_retries=int(os.environ.get("GATEWAY_MAX_WRITE_RETRIES", "3")),
            write_timeout=int(os.environ.get("GATEWAY_WRITE_TIMEOUT", "180")),
        )

    def to_dict(self) -> dict:
        """导出配置为字典（用于调试和状态报告）"""
        return {
            "target_profile": self.target_profile,
            "target_configured": bool(self.target_project),
            "target_project_name": Path(self.target_project).name if self.target_project else "",
            "tia_version": self.tia_version,
            "tiaworker_exe": self.tiaworker_exe,
            "tiacommander_enabled": self.tiacommander_enabled,
            "default_read_provider": self.default_read_provider,
            "default_write_provider": self.default_write_provider,
            "safety_enabled": self.safety_enabled,
            "preview_ttl": self.preview_ttl,
            "debug": self.debug,
        }
