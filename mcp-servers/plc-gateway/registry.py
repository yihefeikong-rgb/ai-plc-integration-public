"""
PLC Engineering Gateway — 统一工具注册表

为所有 MCP 工具提供统一的元数据声明、注册和查询能力。
每个工具必须声明名称、领域、风险等级、读写类型等元数据。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class RiskLevel(Enum):
    """风险等级 L0-L4"""
    L0_READ_ONLY = "L0"       # 纯读取，无需人工确认
    L1_FILE_GEN = "L1"        # 本地文件生成，不修改 TIA
    L2_TIA_EDIT = "L2"        # TIA 工程修改，需 Preview/Apply
    L3_SIM_CONTROL = "L3"     # 仿真控制，需人工确认
    L4_REAL_DEVICE = "L4"     # 真实设备操作，默认禁用


class ToolCategory(Enum):
    """工具领域分类"""
    TIA_PROJECT = "tia.project"
    TIA_BLOCK = "tia.block"
    TIA_TAG = "tia.tag"
    TIA_TYPE = "tia.type"
    TIA_HARDWARE = "tia.hardware"
    TIA_DIAGNOSTICS = "tia.diagnostics"
    PLCSIM = "plcsim"
    PLC_RUNTIME = "plc.runtime"
    LAD = "lad"
    SAFETY = "safety"
    S7 = "s7"
    PIPELINE = "pipeline"
    SYSTEM = "system"


@dataclass
class ToolMetadata:
    """工具元数据声明"""
    name: str
    category: ToolCategory
    risk_level: RiskLevel
    read_only: bool = True
    mutating: bool = False
    requires_preview: bool = False
    requires_confirmation: bool = False
    requires_backup: bool = False
    allowed_targets: list[str] = field(default_factory=lambda: ["isolated_plcsim"])
    timeout_seconds: int = 60
    description: str = ""
    provider: str = "tiaworker"  # 默认提供者

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "read_only": self.read_only,
            "mutating": self.mutating,
            "requires_preview": self.requires_preview,
            "requires_confirmation": self.requires_confirmation,
            "requires_backup": self.requires_backup,
            "allowed_targets": self.allowed_targets,
            "timeout_seconds": self.timeout_seconds,
            "description": self.description,
            "provider": self.provider,
        }


class ToolRegistry:
    """工具注册表 — 管理所有工具的元数据声明和查询"""

    def __init__(self):
        self._tools: dict[str, ToolMetadata] = {}
        self._handlers: dict[str, Callable] = {}

    def register(self, metadata: ToolMetadata, handler: Callable | None = None) -> Callable | None:
        """注册一个工具及其元数据"""
        if metadata.name in self._tools:
            raise ValueError(f"工具 '{metadata.name}' 已注册")
        self._tools[metadata.name] = metadata
        if handler:
            self._handlers[metadata.name] = handler
        return handler

    def get(self, name: str) -> ToolMetadata | None:
        return self._tools.get(name)

    def get_handler(self, name: str) -> Callable | None:
        return self._handlers.get(name)

    def list_tools(self, category: ToolCategory | None = None,
                   risk_level: RiskLevel | None = None,
                   read_only: bool | None = None) -> list[ToolMetadata]:
        """按条件查询工具列表"""
        result = []
        for tool in self._tools.values():
            if category and tool.category != category:
                continue
            if risk_level and tool.risk_level != risk_level:
                continue
            if read_only is not None and tool.read_only != read_only:
                continue
            result.append(tool)
        return result

    def list_by_provider(self, provider: str) -> list[ToolMetadata]:
        return [t for t in self._tools.values() if t.provider == provider]

    def all_tools(self) -> list[ToolMetadata]:
        return list(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def to_dict(self) -> list[dict]:
        return [t.to_dict() for t in self._tools.values()]


# ── 全局注册表实例 ──
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    return _registry


def register_tool(metadata: ToolMetadata, handler: Callable | None = None) -> Callable | None:
    """便捷函数：注册到全局注册表"""
    return _registry.register(metadata, handler)


# ── 预定义工具元数据（按领域分组） ──

# tia.project.*
PROJECT_LIST = ToolMetadata(
    name="tia.project.list", category=ToolCategory.TIA_PROJECT,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="列出所有 TIA 项目")
PROJECT_COMPILE = ToolMetadata(
    name="tia.project.compile", category=ToolCategory.TIA_PROJECT,
    risk_level=RiskLevel.L2_TIA_EDIT, mutating=True,
    requires_preview=True, requires_confirmation=True,
    description="编译 TIA 项目")
PROJECT_SAVE = ToolMetadata(
    name="tia.project.save", category=ToolCategory.TIA_PROJECT,
    risk_level=RiskLevel.L2_TIA_EDIT, mutating=True,
    requires_preview=True, description="保存 TIA 项目")
PROJECT_ARCHIVE = ToolMetadata(
    name="tia.project.archive", category=ToolCategory.TIA_PROJECT,
    risk_level=RiskLevel.L2_TIA_EDIT, mutating=True,
    requires_backup=True, description="归档 TIA 项目")
PROJECT_CLOSE = ToolMetadata(
    name="tia.project.close", category=ToolCategory.TIA_PROJECT,
    risk_level=RiskLevel.L2_TIA_EDIT, mutating=True,
    description="关闭 TIA 项目")

# tia.block.*
BLOCK_LIST = ToolMetadata(
    name="tia.block.list", category=ToolCategory.TIA_BLOCK,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="列出项目中的所有块")
BLOCK_GET_INTERFACE = ToolMetadata(
    name="tia.block.get_interface", category=ToolCategory.TIA_BLOCK,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="读取块接口")
BLOCK_GET_XML = ToolMetadata(
    name="tia.block.get_xml", category=ToolCategory.TIA_BLOCK,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="读取块 XML")
BLOCK_IMPORT = ToolMetadata(
    name="tia.block.import", category=ToolCategory.TIA_BLOCK,
    risk_level=RiskLevel.L2_TIA_EDIT, mutating=True,
    requires_preview=True, requires_confirmation=True, requires_backup=True,
    timeout_seconds=180, description="导入块")
BLOCK_DELETE = ToolMetadata(
    name="tia.block.delete", category=ToolCategory.TIA_BLOCK,
    risk_level=RiskLevel.L2_TIA_EDIT, mutating=True,
    requires_preview=True, requires_confirmation=True, requires_backup=True,
    description="删除块")
BLOCK_COMPILE = ToolMetadata(
    name="tia.block.compile", category=ToolCategory.TIA_BLOCK,
    risk_level=RiskLevel.L2_TIA_EDIT, mutating=True,
    requires_preview=True, description="编译块")
BLOCK_CREATE_LADDER = ToolMetadata(
    name="tia.block.create_ladder", category=ToolCategory.TIA_BLOCK,
    risk_level=RiskLevel.L2_TIA_EDIT, mutating=True,
    requires_preview=True, requires_confirmation=True, requires_backup=True,
    timeout_seconds=300, description="创建梯形图块")

# tia.tag.*
TAG_LIST = ToolMetadata(
    name="tia.tag.list", category=ToolCategory.TIA_TAG,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="列出标签表")
TAG_CREATE = ToolMetadata(
    name="tia.tag.create", category=ToolCategory.TIA_TAG,
    risk_level=RiskLevel.L2_TIA_EDIT, mutating=True,
    requires_preview=True, requires_confirmation=True, requires_backup=True,
    description="创建标签")

# tia.type.*
TYPE_LIST = ToolMetadata(
    name="tia.type.list", category=ToolCategory.TIA_TYPE,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="列出 UDT")
TYPE_CREATE = ToolMetadata(
    name="tia.type.create", category=ToolCategory.TIA_TYPE,
    risk_level=RiskLevel.L2_TIA_EDIT, mutating=True,
    requires_preview=True, requires_confirmation=True,
    description="创建 UDT")

# tia.hardware.*
HARDWARE_LIST = ToolMetadata(
    name="tia.hardware.list", category=ToolCategory.TIA_HARDWARE,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="列出硬件设备")
HARDWARE_INFO = ToolMetadata(
    name="tia.hardware.info", category=ToolCategory.TIA_HARDWARE,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="读取硬件信息")

# tia.diagnostics.*
DIAG_COMPILE_ERRORS = ToolMetadata(
    name="tia.diagnostics.compile_errors", category=ToolCategory.TIA_DIAGNOSTICS,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="读取编译错误")
DIAG_CROSS_REF = ToolMetadata(
    name="tia.diagnostics.cross_ref", category=ToolCategory.TIA_DIAGNOSTICS,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="交叉引用查询")

# plcsim.*
PLCSIM_LIST = ToolMetadata(
    name="plcsim.list_instances", category=ToolCategory.PLCSIM,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="列出 PLCSIM 实例")
PLCSIM_START = ToolMetadata(
    name="plcsim.start", category=ToolCategory.PLCSIM,
    risk_level=RiskLevel.L3_SIM_CONTROL, mutating=True,
    requires_confirmation=True, allowed_targets=["isolated_plcsim"],
    description="启动 PLCSIM 实例")
PLCSIM_DOWNLOAD = ToolMetadata(
    name="plcsim.download", category=ToolCategory.PLCSIM,
    risk_level=RiskLevel.L3_SIM_CONTROL, mutating=True,
    requires_preview=True, requires_confirmation=True, requires_backup=True,
    allowed_targets=["isolated_plcsim"], timeout_seconds=300,
    description="下载到 PLCSIM")
PLCSIM_GOLDEN_RESTORE = ToolMetadata(
    name="plcsim.golden_restore", category=ToolCategory.PLCSIM,
    risk_level=RiskLevel.L3_SIM_CONTROL, mutating=True,
    requires_confirmation=True, allowed_targets=["isolated_plcsim"],
    description="从黄金备份恢复")

# plc.runtime.*
RUNTIME_READ = ToolMetadata(
    name="plc.runtime.read", category=ToolCategory.PLC_RUNTIME,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="读取 PLC 运行态数据")
RUNTIME_WRITE = ToolMetadata(
    name="plc.runtime.write", category=ToolCategory.PLC_RUNTIME,
    risk_level=RiskLevel.L4_REAL_DEVICE, mutating=True,
    requires_confirmation=True, allowed_targets=[],
    description="写入 PLC 运行态数据（默认禁用）")

# lad.*
LAD_GENERATE = ToolMetadata(
    name="lad.generate", category=ToolCategory.LAD,
    risk_level=RiskLevel.L1_FILE_GEN,
    description="生成梯形图 LadderSpec")
LAD_DESCRIBE = ToolMetadata(
    name="lad.describe_block", category=ToolCategory.LAD,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="解析并描述块逻辑")

# s7.*
S7_READ = ToolMetadata(
    name="s7.read", category=ToolCategory.S7,
    risk_level=RiskLevel.L0_READ_ONLY, read_only=True,
    description="S7 只读读取")
S7_WRITE = ToolMetadata(
    name="s7.write", category=ToolCategory.S7,
    risk_level=RiskLevel.L4_REAL_DEVICE, mutating=True,
    requires_confirmation=True, allowed_targets=[],
    description="S7 写入（默认禁用）")

# pipeline.*
PIPELINE_RUN = ToolMetadata(
    name="pipeline.run", category=ToolCategory.PIPELINE,
    risk_level=RiskLevel.L3_SIM_CONTROL, mutating=True,
    requires_confirmation=True, allowed_targets=["isolated_plcsim"],
    timeout_seconds=600, description="执行端到端流水线")


def register_default_tools() -> None:
    """注册所有预定义工具到全局注册表（注册 handler 由各工具模块自行完成）"""
    _all = [
        PROJECT_LIST, PROJECT_COMPILE, PROJECT_SAVE, PROJECT_ARCHIVE, PROJECT_CLOSE,
        BLOCK_LIST, BLOCK_GET_INTERFACE, BLOCK_GET_XML, BLOCK_IMPORT, BLOCK_DELETE,
        BLOCK_COMPILE, BLOCK_CREATE_LADDER,
        TAG_LIST, TAG_CREATE,
        TYPE_LIST, TYPE_CREATE,
        HARDWARE_LIST, HARDWARE_INFO,
        DIAG_COMPILE_ERRORS, DIAG_CROSS_REF,
        PLCSIM_LIST, PLCSIM_START, PLCSIM_DOWNLOAD, PLCSIM_GOLDEN_RESTORE,
        RUNTIME_READ, RUNTIME_WRITE,
        LAD_GENERATE, LAD_DESCRIBE,
        S7_READ, S7_WRITE,
        PIPELINE_RUN,
    ]
    for meta in _all:
        try:
            _registry.register(meta)
        except ValueError:
            pass  # 已注册则跳过