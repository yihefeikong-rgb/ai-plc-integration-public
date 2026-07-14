"""自然语言到 PLCSIM 主链工作流测试。"""

import pytest

from orchestrator.core import OrchestratorEngine
from orchestrator.workflows.nl_to_plcsim_pipeline import (
    DEFAULT_ACCEPTANCE_PROMPT,
    register_nl_to_plcsim_pipeline_workflow,
)


def _make_engine() -> OrchestratorEngine:
    engine = OrchestratorEngine()
    register_nl_to_plcsim_pipeline_workflow(engine)
    engine.register_mocks({
        "tia-mcp.create_ladder_block": lambda description, block_name: {
            "status": "ok",
            "blockName": block_name,
            "networks": 3,
            "xmlPath": "C:/out/Motor.xml",
        },
        "tia-mcp.call_fb_in_ob1": lambda fb_names: {
            "status": "ok",
            "fb_names": fb_names,
        },
        "plc-mcp-bridge.plc_compile_project": lambda: {
            "ok": True,
            "success": True,
            "errors": 0,
        },
        "plc-mcp-bridge.plc_download_project": lambda method="auto", compile_first=False: {
            "ok": True,
            "success": True,
        },
        "plc-mcp-bridge.s7_connect": lambda: "✅ 已连接",
        "plc-mcp-bridge.s7_read": lambda address: f"📍 {address} = False",
        "plc-mcp-bridge.s7_disconnect": lambda: "✅ 已断开",
        "plc-mcp-bridge.plc_fio_write_config": lambda instance_name="factoryio": "✅ 配置已写入",
        "plc-mcp-bridge.plc_fio_launch": lambda: "✅ Factory I/O 已启动",
    })
    return engine


class TestNlToPlcsimPipeline:
    def test_workflow_registered(self):
        engine = OrchestratorEngine()
        register_nl_to_plcsim_pipeline_workflow(engine)

        assert "nl_to_plcsim_pipeline" in engine.list_workflows()

    @pytest.mark.asyncio
    async def test_success_path_runs_expected_steps(self):
        engine = _make_engine()

        result = await engine.run_async(
            "nl_to_plcsim_pipeline",
            input={
                "description": DEFAULT_ACCEPTANCE_PROMPT,
                "block_name": "MotorFwdRev",
                "launch_fio": True,
            },
        )

        assert result.ok is True
        assert [step.tool for step in result.steps] == [
            "tia-mcp.create_ladder_block",
            "tia-mcp.call_fb_in_ob1",
            "plc-mcp-bridge.plc_compile_project",
            "plc-mcp-bridge.plc_download_project",
            "plc-mcp-bridge.s7_connect",
            "plc-mcp-bridge.s7_read",
            "plc-mcp-bridge.s7_disconnect",
            "plc-mcp-bridge.plc_fio_write_config",
            "plc-mcp-bridge.plc_fio_launch",
        ]

    @pytest.mark.asyncio
    async def test_compile_failure_stops_before_download(self):
        engine = _make_engine()
        engine.register_mock("plc-mcp-bridge.plc_compile_project", lambda: {
            "ok": False,
            "success": False,
            "errors": 2,
            "message": "编译失败",
        })

        result = await engine.run_async(
            "nl_to_plcsim_pipeline",
            input={"description": DEFAULT_ACCEPTANCE_PROMPT},
        )

        assert result.ok is False
        assert "编译失败" in result.error
        assert "plc-mcp-bridge.plc_download_project" not in [s.tool for s in result.steps]

    @pytest.mark.asyncio
    async def test_launch_fio_false_skips_fio_steps(self):
        engine = _make_engine()

        result = await engine.run_async(
            "nl_to_plcsim_pipeline",
            input={"description": DEFAULT_ACCEPTANCE_PROMPT, "launch_fio": False},
        )

        assert result.ok is True
        tools = [step.tool for step in result.steps]
        assert "plc-mcp-bridge.plc_fio_write_config" not in tools
        assert "plc-mcp-bridge.plc_fio_launch" not in tools

