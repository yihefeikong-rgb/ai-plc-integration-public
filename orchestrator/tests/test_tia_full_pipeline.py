"""
测试 TIA 全流水线工作流 (tia_full_pipeline)。
"""
import pytest

from orchestrator.core import OrchestratorEngine
from orchestrator.workflows.tia_full_pipeline import (
    register_tia_full_pipeline_workflow,
    build_pipeline_steps,
)


def _make_engine() -> OrchestratorEngine:
    """创建引擎并注册 tia_full_pipeline 工作流及全部 mock 工具。"""
    engine = OrchestratorEngine()
    register_tia_full_pipeline_workflow(engine)

    engine.register_mocks({
        "plc-mcp-bridge.plc_create_project": lambda name, path: {
            "project_id": "proj-001",
        },
        "plc-mcp-bridge.plc_create_instance": lambda project_path, plc_ip, rack, slot: {
            "instance_id": "inst-001",
        },
        "tia-mcp.generate_scl_code": lambda prompt: {
            "scl_path": "/tmp/motor_ctrl.scl",
            "code": "FUNCTION_BLOCK \"MotorCtrl\"",
        },
        "tia-mcp.import_scl_file": lambda scl_path, project_path: {
            "blocks_imported": ["MotorCtrl"],
        },
        "plc-mcp-bridge.plc_compile_project": lambda project_path: {
            "ok": True,
            "errors": 0,
        },
        "plc-mcp-bridge.plc_download_project": lambda project_path, plc_ip: {
            "ok": True,
        },
    })
    return engine


# ============================================================================
# 注册测试
# ============================================================================


class TestRegistration:
    """工作流注册"""

    def test_workflow_registered(self):
        engine = OrchestratorEngine()
        register_tia_full_pipeline_workflow(engine)
        assert "tia_full_pipeline" in engine.list_workflows()

    def test_workflow_retrievable(self):
        engine = OrchestratorEngine()
        register_tia_full_pipeline_workflow(engine)
        assert engine.get_workflow("tia_full_pipeline") is not None


# ============================================================================
# 全量成功测试
# ============================================================================


class TestFullPipelineSuccess:
    """所有步骤成功"""

    @pytest.mark.asyncio
    async def test_all_six_steps_ok(self):
        engine = _make_engine()
        result = await engine.run_async(
            "tia_full_pipeline",
            input={
                "project_name": "TestProject",
                "project_path": "C:/Projects/TestProject",
                "scl_prompt": "生成电机控制 FB",
            },
        )
        assert result.ok is True
        assert len(result.steps) == 6
        for step in result.steps:
            assert step.ok is True, f"步骤 {step.tool} 失败: {step.error}"

    @pytest.mark.asyncio
    async def test_step_tools_correct_order(self):
        engine = _make_engine()
        result = await engine.run_async(
            "tia_full_pipeline",
            input={
                "project_name": "TestProject",
                "project_path": "C:/Projects/TestProject",
                "scl_prompt": "生成电机控制 FB",
            },
        )
        expected_tools = [
            "plc-mcp-bridge.plc_create_project",
            "plc-mcp-bridge.plc_create_instance",
            "tia-mcp.generate_scl_code",
            "tia-mcp.import_scl_file",
            "plc-mcp-bridge.plc_compile_project",
            "plc-mcp-bridge.plc_download_project",
        ]
        actual_tools = [s.tool for s in result.steps]
        assert actual_tools == expected_tools

    @pytest.mark.asyncio
    async def test_return_value_contains_expected_fields(self):
        engine = _make_engine()
        result = await engine.run_async(
            "tia_full_pipeline",
            input={
                "project_name": "TestProject",
                "project_path": "C:/Projects/TestProject",
                "scl_prompt": "生成电机控制 FB",
            },
        )
        assert result.ok is True
        # run_async 返回 WorkflowResult，步骤的 data 记录在 StepResult.data
        step1_data = result.steps[0].data
        assert step1_data["project_id"] == "proj-001"


# ============================================================================
# 部分失败测试
# ============================================================================


class TestPartialFailure:
    """步骤失败时中止后续步骤"""

    @pytest.mark.asyncio
    async def test_step3_failure_stops_pipeline(self):
        """第 3 步（generate_scl_code）失败 → 只执行前 2 步"""
        engine = OrchestratorEngine()
        register_tia_full_pipeline_workflow(engine)

        def failing_generate(**kwargs):
            raise RuntimeError("SCL 生成失败：提示词无效")

        engine.register_mocks({
            "plc-mcp-bridge.plc_create_project": lambda name, path: {"project_id": "p1"},
            "plc-mcp-bridge.plc_create_instance": lambda **kw: {"instance_id": "i1"},
            "tia-mcp.generate_scl_code": failing_generate,
            "tia-mcp.import_scl_file": lambda **kw: {"blocks_imported": []},
            "plc-mcp-bridge.plc_compile_project": lambda **kw: {"ok": True},
            "plc-mcp-bridge.plc_download_project": lambda **kw: {"ok": True},
        })

        result = await engine.run_async(
            "tia_full_pipeline",
            input={
                "project_name": "FailProject",
                "project_path": "C:/Projects/FailProject",
                "scl_prompt": "无效提示词",
            },
        )

        assert result.ok is False
        # 步骤 1 和 2 成功，步骤 3 失败，4-6 未执行
        assert len(result.steps) == 3
        assert result.steps[0].ok is True
        assert result.steps[1].ok is True
        assert result.steps[2].ok is False
        assert "SCL 生成失败" in result.steps[2].error

    @pytest.mark.asyncio
    async def test_step1_failure_no_further_steps(self):
        """第 1 步失败 → 只有 1 个步骤记录"""
        engine = OrchestratorEngine()
        register_tia_full_pipeline_workflow(engine)

        def failing_create(**kwargs):
            raise ValueError("项目路径无效")

        engine.register_mock("plc-mcp-bridge.plc_create_project", failing_create)

        result = await engine.run_async(
            "tia_full_pipeline",
            input={
                "project_name": "Bad",
                "project_path": "",
                "scl_prompt": "test",
            },
        )

        assert result.ok is False
        assert len(result.steps) == 1
        assert result.steps[0].ok is False
        assert "项目路径无效" in result.steps[0].error


# ============================================================================
# 数据传递测试
# ============================================================================


class TestDataPassing:
    """步骤间数据正确传递"""

    @pytest.mark.asyncio
    async def test_scl_path_passed_to_import_step(self):
        """步骤 3 生成的 scl_path 应传递给步骤 4"""
        engine = OrchestratorEngine()
        register_tia_full_pipeline_workflow(engine)

        received_scl_path = {}

        engine.register_mocks({
            "plc-mcp-bridge.plc_create_project": lambda name, path: {"project_id": "p1"},
            "plc-mcp-bridge.plc_create_instance": lambda **kw: {"instance_id": "i1"},
            "tia-mcp.generate_scl_code": lambda prompt: {
                "scl_path": "/special/path/custom.scl",
            },
            "tia-mcp.import_scl_file": lambda scl_path, project_path: {
                "captured_scl_path": scl_path,
                "blocks_imported": [],
            },
            "plc-mcp-bridge.plc_compile_project": lambda project_path: {"ok": True},
            "plc-mcp-bridge.plc_download_project": lambda project_path, plc_ip: {"ok": True},
        })

        result = await engine.run_async(
            "tia_full_pipeline",
            input={
                "project_name": "DataTest",
                "project_path": "C:/Projects/DataTest",
                "scl_prompt": "生成 FB",
            },
        )

        assert result.ok is True
        # 步骤 4 (import_scl_file) 的 data 应包含从步骤 3 传递过来的 scl_path
        step4_data = result.steps[3].data
        assert step4_data["captured_scl_path"] == "/special/path/custom.scl"


# ============================================================================
# build_pipeline_steps 测试
# ============================================================================


class TestBuildPipelineSteps:
    """build_pipeline_steps 辅助函数"""

    def test_returns_six_steps(self):
        steps = build_pipeline_steps(
            project_name="Test",
            project_path="C:/Test",
            scl_prompt="生成 FB",
        )
        assert len(steps) == 6

    def test_each_step_has_tool_and_args(self):
        steps = build_pipeline_steps(
            project_name="Test",
            project_path="C:/Test",
            scl_prompt="生成 FB",
        )
        for step in steps:
            assert "tool" in step
            assert "args" in step
            assert isinstance(step["args"], dict)

    def test_tools_match_workflow_order(self):
        steps = build_pipeline_steps(
            project_name="Test",
            project_path="C:/Test",
            scl_prompt="生成 FB",
        )
        expected_tools = [
            "plc-mcp-bridge.plc_create_project",
            "plc-mcp-bridge.plc_create_instance",
            "tia-mcp.generate_scl_code",
            "tia-mcp.import_scl_file",
            "plc-mcp-bridge.plc_compile_project",
            "plc-mcp-bridge.plc_download_project",
        ]
        actual_tools = [s["tool"] for s in steps]
        assert actual_tools == expected_tools

    def test_custom_plc_ip_and_rack_slot(self):
        steps = build_pipeline_steps(
            project_name="Test",
            project_path="C:/Test",
            scl_prompt="生成 FB",
            plc_ip="10.0.0.1",
            rack=2,
            slot=3,
        )
        # 步骤 2 (plc_create_instance) 的 args 应包含自定义参数
        step2_args = steps[1]["args"]
        assert step2_args["plc_ip"] == "10.0.0.1"
        assert step2_args["rack"] == 2
        assert step2_args["slot"] == 3

    def test_default_plc_ip(self):
        steps = build_pipeline_steps(
            project_name="Test",
            project_path="C:/Test",
            scl_prompt="生成 FB",
        )
        step2_args = steps[1]["args"]
        assert step2_args["plc_ip"] == "192.168.0.110"
        assert step2_args["rack"] == 0
        assert step2_args["slot"] == 1

    def test_download_step_includes_plc_ip(self):
        steps = build_pipeline_steps(
            project_name="Test",
            project_path="C:/Test",
            scl_prompt="生成 FB",
            plc_ip="10.0.0.5",
        )
        step6_args = steps[5]["args"]
        assert step6_args["plc_ip"] == "10.0.0.5"
