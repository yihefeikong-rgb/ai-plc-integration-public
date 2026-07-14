"""
预定义工作流集合。
"""
from __future__ import annotations

from typing import Any


def register_all_workflows(engine: Any) -> None:
    """向编排引擎注册所有工作流。

    新增工作流时，在此函数中添加对应的 register_* 调用即可。
    """
    from orchestrator.workflows.s7_monitor import register_s7_monitor_workflow
    from orchestrator.workflows.tia_multi_block_pipeline import register_tia_multi_block_pipeline_workflow
    from orchestrator.workflows.nl_to_plcsim_pipeline import register_nl_to_plcsim_pipeline_workflow
    from orchestrator.workflows.robot_pick_place import register_robot_pick_place_workflow
    from orchestrator.workflows.robot_monitor import register_robot_monitor_workflow

    register_s7_monitor_workflow(engine)
    register_tia_multi_block_pipeline_workflow(engine)
    register_nl_to_plcsim_pipeline_workflow(engine)
    register_robot_pick_place_workflow(engine)
    register_robot_monitor_workflow(engine)

    # tia_download / tia_full_pipeline 是历史工作流：它们允许调用方提供
    # project_path / plc_ip，且工具签名已与当前受控 MCP 契约脱节。保留源文件
    # 仅供离线迁移测试，绝不在运行时 API 中注册；受控入口为 nl_to_plcsim_pipeline。
