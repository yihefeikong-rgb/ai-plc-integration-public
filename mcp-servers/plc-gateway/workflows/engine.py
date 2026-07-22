"""
PLC Engineering Gateway — 统一编排工作流

工作流状态：
  DRAFT → VALIDATED → AWAITING_REVIEW → PREVIEWED
  → AWAITING_CONFIRMATION → APPLYING → COMPILING
  → VERIFYING → SUCCEEDED / FAILED
  → ROLLING_BACK → ROLLED_BACK
  → RECONCILE_REQUIRED

预定义工作流：
  A: 生成 PLC 程序候选（自然语言 → LAD → 用户审查，不修改 TIA）
  B: 导入测试项目（确认 → Preview → Apply → 编译）
  C: 受控 PLCSIM 验收（编译 → 下载 → snap7 回读 → 验收报告）
  D: 修改已有块（读取 → AST → Patch → Diff → Preview → Apply → 编译）
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class WorkflowStatus(Enum):
    """工作流状态"""
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    PREVIEWED = "PREVIEWED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    APPLYING = "APPLYING"
    COMPILING = "COMPILING"
    VERIFYING = "VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    RECONCILE_REQUIRED = "RECONCILE_REQUIRED"


# 工作流状态转换规则
_WORKFLOW_TRANSITIONS: dict[WorkflowStatus, list[WorkflowStatus]] = {
    WorkflowStatus.DRAFT: [WorkflowStatus.VALIDATED, WorkflowStatus.FAILED],
    WorkflowStatus.VALIDATED: [WorkflowStatus.AWAITING_REVIEW, WorkflowStatus.FAILED],
    WorkflowStatus.AWAITING_REVIEW: [WorkflowStatus.PREVIEWED, WorkflowStatus.FAILED, WorkflowStatus.DRAFT],
    WorkflowStatus.PREVIEWED: [WorkflowStatus.AWAITING_CONFIRMATION, WorkflowStatus.FAILED],
    WorkflowStatus.AWAITING_CONFIRMATION: [WorkflowStatus.APPLYING, WorkflowStatus.FAILED, WorkflowStatus.DRAFT],
    WorkflowStatus.APPLYING: [WorkflowStatus.COMPILING, WorkflowStatus.FAILED, WorkflowStatus.ROLLING_BACK],
    WorkflowStatus.COMPILING: [WorkflowStatus.VERIFYING, WorkflowStatus.FAILED, WorkflowStatus.ROLLING_BACK],
    WorkflowStatus.VERIFYING: [WorkflowStatus.SUCCEEDED, WorkflowStatus.FAILED, WorkflowStatus.ROLLING_BACK],
    WorkflowStatus.SUCCEEDED: [],
    WorkflowStatus.FAILED: [WorkflowStatus.DRAFT, WorkflowStatus.ROLLING_BACK],
    WorkflowStatus.ROLLING_BACK: [WorkflowStatus.ROLLED_BACK, WorkflowStatus.RECONCILE_REQUIRED],
    WorkflowStatus.ROLLED_BACK: [WorkflowStatus.DRAFT],
    WorkflowStatus.RECONCILE_REQUIRED: [WorkflowStatus.DRAFT],
}


@dataclass
class WorkflowStep:
    """工作流步骤记录"""
    name: str
    status: str = "pending"
    started_at: float = 0.0
    completed_at: float = 0.0
    result: dict | None = None
    error: str | None = None


@dataclass
class WorkflowInstance:
    """工作流实例"""
    workflow_id: str = ""
    name: str = ""
    status: WorkflowStatus = WorkflowStatus.DRAFT
    steps: list[WorkflowStep] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.workflow_id:
            self.workflow_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()
            self.updated_at = self.created_at

    def transition(self, to: WorkflowStatus) -> bool:
        """尝试状态转换"""
        if to in _WORKFLOW_TRANSITIONS.get(self.status, []):
            self.status = to
            self.updated_at = time.time()
            return True
        return False

    def add_step(self, name: str) -> WorkflowStep:
        step = WorkflowStep(name=name, started_at=time.time())
        self.steps.append(step)
        return step

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "status": self.status.value,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status,
                    "result": s.result,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class WorkflowEngine:
    """工作流引擎 — 管理工作流实例和状态转换"""

    def __init__(self):
        self._instances: dict[str, WorkflowInstance] = {}

    def create(self, name: str, metadata: dict | None = None) -> WorkflowInstance:
        instance = WorkflowInstance(name=name, metadata=metadata or {})
        self._instances[instance.workflow_id] = instance
        return instance

    def get(self, workflow_id: str) -> WorkflowInstance | None:
        return self._instances.get(workflow_id)

    def list_active(self) -> list[WorkflowInstance]:
        terminal = {WorkflowStatus.SUCCEEDED, WorkflowStatus.FAILED,
                    WorkflowStatus.ROLLED_BACK}
        return [w for w in self._instances.values()
                if w.status not in terminal]


# ── 全局工作流引擎实例 ──
_engine = WorkflowEngine()


def get_workflow_engine() -> WorkflowEngine:
    return _engine