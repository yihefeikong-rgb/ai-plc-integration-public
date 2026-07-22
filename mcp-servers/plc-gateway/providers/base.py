"""
PLC Engineering Gateway — Provider 抽象基类

定义所有 TIA 后端提供者（TiaWorker、TiaCommander 等）的统一接口。
Gateway 不直接依赖某一种 TIA 实现，而是通过此接口选择提供者。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResult:
    """Provider 操作的标准返回格式"""
    ok: bool
    status: str = "success"
    operation: str = ""
    operation_id: str = ""
    result: dict | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    reconcile_required: bool = False

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "status": self.status if self.ok else "error",
            "operation": self.operation,
            "operation_id": self.operation_id,
            "result": self.result or {},
            "warnings": self.warnings,
            "error": self.error if not self.ok else None,
            "reconcile_required": self.reconcile_required,
        }


class TiaProvider(ABC):
    """TIA 后端提供者抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """提供者名称: tiaworker / tiacommander"""
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """提供者当前是否可用"""
        ...

    @abstractmethod
    def get_project_info(self) -> ProviderResult:
        """获取项目信息"""
        ...

    @abstractmethod
    def list_blocks(self) -> ProviderResult:
        """列出项目中的所有块"""
        ...

    @abstractmethod
    def get_block_xml(self, block_name: str) -> ProviderResult:
        """读取块的 XML"""
        ...

    @abstractmethod
    def get_block_interface(self, block_name: str) -> ProviderResult:
        """读取块接口"""
        ...

    @abstractmethod
    def compile_project(self) -> ProviderResult:
        """编译项目"""
        ...

    @abstractmethod
    def list_devices(self) -> ProviderResult:
        """列出设备"""
        ...

    # ── 可选实现的写操作 ──

    def create_block(self, block_name: str, lang: str = "SCL") -> ProviderResult:
        """创建块（可选实现）"""
        raise NotImplementedError(f"{self.name} 不支持 create_block")

    def import_block_xml(self, xml_path: str) -> ProviderResult:
        """导入块 XML（可选实现）"""
        raise NotImplementedError(f"{self.name} 不支持 import_block_xml")

    def delete_block(self, block_name: str) -> ProviderResult:
        """删除块（可选实现）"""
        raise NotImplementedError(f"{self.name} 不支持 delete_block")

    def preview_patch(self, patch: dict) -> ProviderResult:
        """预览网络级 Patch（可选实现）"""
        raise NotImplementedError(f"{self.name} 不支持 preview_patch")

    def apply_patch(self, patch: dict) -> ProviderResult:
        """应用网络级 Patch（可选实现）"""
        raise NotImplementedError(f"{self.name} 不支持 apply_patch")