"""
预定义工作流集合。
"""
from __future__ import annotations

from typing import Any


def register_all_workflows(engine: Any) -> None:
    """向编排引擎注册所有工作流。

    新增工作流时，在此函数中添加对应的 register_* 调用即可。
    """
    from orchestrator.workflows.tia_download import register_tia_download_workflow
    from orchestrator.workflows.s7_monitor import register_s7_monitor_workflow
    from orchestrator.workflows.tia_full_pipeline import register_tia_full_pipeline_workflow
    from orchestrator.workflows.robot_pick_place import register_robot_pick_place_workflow
    from orchestrator.workflows.robot_monitor import register_robot_monitor_workflow

    register_tia_download_workflow(engine)
    register_s7_monitor_workflow(engine)
    register_tia_full_pipeline_workflow(engine)
    register_robot_pick_place_workflow(engine)
    register_robot_monitor_workflow(engine)
