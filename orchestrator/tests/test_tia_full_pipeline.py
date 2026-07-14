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
        "tia-mcp.generate_scl_code": lambda description: {
            "status": "ok",
            "data": {"scl_code": "FUNCTION_BLOCK \"MotorCtrl\"...", "block_name": "MotorCtrl"},
            "scl_code": "FUNCTION_BLOCK \"MotorCtrl\"...",
            "block_name": "MotorCtrl",
        },
        "tia-mcp.import_scl_file": lambda scl_code, block_name, project_path, replace=True: {
            "blocks_imported": ["MotorCtrl"],
        },
        "plc-mcp-bridge.plc_compile_project": lambda project_path: {
            "ok": True,
            "success": True,
            "errors": 0,
            "error_list": [],
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
            "tia-mcp.import_scl_file": lambda scl_code, block_name, project_path, replace=True: {"blocks_imported": []},
            "plc-mcp-bridge.plc_compile_project": lambda **kw: {"ok": True, "success": True, "errors": 0, "error_list": []},
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
    async def test_scl_code_passed_to_import_step(self):
        """步骤 3 生成的 scl_code 应传递给步骤 4"""
        engine = OrchestratorEngine()
        register_tia_full_pipeline_workflow(engine)

        engine.register_mocks({
            "plc-mcp-bridge.plc_create_project": lambda name, path: {"project_id": "p1"},
            "plc-mcp-bridge.plc_create_instance": lambda **kw: {"instance_id": "i1"},
            "tia-mcp.generate_scl_code": lambda description: {
                "status": "ok",
                "data": {"scl_code": "FUNCTION_BLOCK Custom...", "block_name": "CustomBlock"},
                "scl_code": "FUNCTION_BLOCK Custom...",
                "block_name": "CustomBlock",
            },
            "tia-mcp.import_scl_file": lambda scl_code, block_name, project_path, replace=True: {
                "captured_scl_code": scl_code,
                "captured_block_name": block_name,
                "blocks_imported": [],
            },
            "plc-mcp-bridge.plc_compile_project": lambda project_path: {"ok": True, "success": True, "errors": 0, "error_list": []},
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
        # 步骤 4 (import_scl_file) 应收到步骤 3 生成的 scl_code 和 block_name
        step4_data = result.steps[3].data
        assert step4_data["captured_scl_code"] == "FUNCTION_BLOCK Custom..."
        assert step4_data["captured_block_name"] == "CustomBlock"


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

    def test_step3_uses_description_not_prompt(self):
        steps = build_pipeline_steps(
            project_name="Test",
            project_path="C:/Test",
            scl_prompt="生成 FB",
        )
        step3_args = steps[2]["args"]
        assert "description" in step3_args
        assert step3_args["description"] == "生成 FB"
        assert "prompt" not in step3_args

    def test_step4_uses_scl_code_and_block_name(self):
        steps = build_pipeline_steps(
            project_name="Test",
            project_path="C:/Test",
            scl_prompt="生成 FB",
        )
        step4_args = steps[3]["args"]
        assert "scl_code" in step4_args
        assert "block_name" in step4_args
        assert "project_path" in step4_args
        assert "scl_path" not in step4_args

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


# ============================================================================
# 编译重试逻辑测试
# ============================================================================


class TestCompileFailure:
    """编译工具明确失败时，工作流必须停止而非盲目重试。"""

    def _make_retry_engine(self, compile_results: list[dict]):
        """创建引擎用于测试重试逻辑。

        compile_results: 依次返回的编译结果列表（第 1 次尝试用 compile_results[0]，以此类推）
        """
        engine = OrchestratorEngine()
        register_tia_full_pipeline_workflow(engine)

        attempt_counter = {"count": 0}

        def compile_with_retry_count(project_path):
            idx = attempt_counter["count"]
            attempt_counter["count"] += 1
            if idx < len(compile_results):
                return compile_results[idx]
            # 超出预定义结果数，返回成功
            return {"ok": True, "errors": 0}

        engine.register_mocks({
            "plc-mcp-bridge.plc_create_project": lambda name, path: {"project_id": "proj-retry"},
            "plc-mcp-bridge.plc_create_instance": lambda **kw: {"instance_id": "i1"},
            "tia-mcp.generate_scl_code": lambda description: {
                "status": "ok",
                "data": {"scl_code": f"FB RetryAttempt {attempt_counter['count']}", "block_name": "RetryFB"},
                "scl_code": f"FB RetryAttempt {attempt_counter['count']}",
                "block_name": "RetryFB",
            },
            "tia-mcp.import_scl_file": lambda scl_code, block_name, project_path, replace=True: {
                "blocks_imported": ["RetryFB"],
            },
            "plc-mcp-bridge.plc_compile_project": compile_with_retry_count,
            "plc-mcp-bridge.plc_download_project": lambda project_path, plc_ip: {"ok": True},
        })
        return engine

    @pytest.mark.asyncio
    async def test_compile_pass_no_retry(self):
        """编译一次通过时，不触发重试，只执行一组步骤 3-4-5"""
        engine = self._make_retry_engine([
            {"ok": True, "success": True, "errors": 0, "error_list": []},
        ])

        result = await engine.run_async(
            "tia_full_pipeline",
            input={"project_name": "T", "project_path": "C:/T", "scl_prompt": "test"},
        )
        assert result.ok is True
        # 步骤: 1-create, 2-instance, 3-gen, 4-import, 5-compile, 6-download = 6 步，无重试
        assert len(result.steps) == 6
        data = result.steps[-1].data  # 最终返回的数据
        assert result.steps[4].ok is True  # compile 成功

    @pytest.mark.asyncio
    async def test_compile_fail_once_then_pass(self):
        """明确编译失败后不得重试或继续下载。"""
        engine = self._make_retry_engine([
            {"ok": False, "success": False, "errors": 2, "error_list": [
                {"line": 5, "file": "RetryFB.scl", "text": "语法错误", "severity": "error"},
                {"line": 12, "file": "RetryFB.scl", "text": "变量未声明", "severity": "error"},
            ]},
            {"ok": True, "success": True, "errors": 0, "error_list": []},
        ])

        result = await engine.run_async(
            "tia_full_pipeline",
            input={"project_name": "T", "project_path": "C:/T", "scl_prompt": "test"},
        )
        assert result.ok is False
        assert len(result.steps) == 5
        assert result.steps[-1].ok is False
        assert "plc-mcp-bridge.plc_download_project" not in [s.tool for s in result.steps]

    @pytest.mark.asyncio
    async def test_compile_fail_three_times(self):
        """第一次明确失败即停止，后续编译结果不得被消费。"""
        error_list = [
            {"line": 5, "file": "X.scl", "text": "语法错误", "severity": "error"},
        ]
        engine = self._make_retry_engine([
            {"ok": False, "success": False, "errors": 1, "error_list": error_list},
            {"ok": False, "success": False, "errors": 1, "error_list": error_list},
            {"ok": False, "success": False, "errors": 1, "error_list": error_list},
        ])

        result = await engine.run_async(
            "tia_full_pipeline",
            input={"project_name": "T", "project_path": "C:/T", "scl_prompt": "test"},
        )
        assert result.ok is False
        assert len(result.steps) == 5
        tools_executed = [s.tool for s in result.steps]
        assert "plc-mcp-bridge.plc_download_project" not in tools_executed

    @pytest.mark.asyncio
    async def test_retry_preserves_error_details(self):
        """失败细节不能触发自动重试或下载。"""
        first_errors = [
            {"line": 5, "file": "A.scl", "text": "语法错误: 意外的 '}',", "severity": "error"},
            {"line": 8, "file": "A.scl", "text": "变量未声明", "severity": "error"},
        ]
        second_errors = [
            {"line": 3, "file": "A.scl", "text": "类型不匹配", "severity": "error"},
        ]
        engine = self._make_retry_engine([
            {"ok": False, "success": False, "errors": 2, "error_list": first_errors},
            {"ok": False, "success": False, "errors": 1, "error_list": second_errors},
            {"ok": False, "success": False, "errors": 1, "error_list": [
                {"line": 10, "file": "A.scl", "text": "未知标识符", "severity": "error"},
            ]},
        ])

        result = await engine.run_async(
            "tia_full_pipeline",
            input={"project_name": "T", "project_path": "C:/T", "scl_prompt": "test"},
        )
        assert result.ok is False
        assert len(result.steps) == 5
        tools_executed = [s.tool for s in result.steps]
        assert "plc-mcp-bridge.plc_download_project" not in tools_executed

    @pytest.mark.asyncio
    async def test_compile_fail_no_error_list_fallback(self):
        """编译失败但无错误明细时也必须停止。"""
        engine = self._make_retry_engine([
            {"ok": False, "success": False, "errors": 5},
            {"ok": False, "success": False, "errors": 3},
            {"ok": False, "success": False, "errors": 1},
        ])

        result = await engine.run_async(
            "tia_full_pipeline",
            input={"project_name": "T", "project_path": "C:/T", "scl_prompt": "test"},
        )
        assert result.ok is False
        assert len(result.steps) == 5
        tools_executed = [s.tool for s in result.steps]
        assert "plc-mcp-bridge.plc_download_project" not in tools_executed

    @pytest.mark.asyncio
    async def test_step1_failure_no_retry(self):
        """步骤 1 失败不触发编译重试"""
        engine = OrchestratorEngine()
        register_tia_full_pipeline_workflow(engine)

        def failing_create(**kwargs):
            raise ValueError("项目路径无效")

        engine.register_mock("plc-mcp-bridge.plc_create_project", failing_create)

        result = await engine.run_async(
            "tia_full_pipeline",
            input={"project_name": "Bad", "project_path": "", "scl_prompt": "test"},
        )
        assert result.ok is False
        assert len(result.steps) == 1  # 只有步骤 1 失败，无重试
