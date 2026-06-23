"""
测试多块依赖顺序工作流 (tia_multi_block_pipeline)。
"""
import pytest

from orchestrator.core import OrchestratorEngine
from orchestrator.workflows.tia_multi_block_pipeline import (
    register_tia_multi_block_pipeline_workflow,
    _sort_blocks_by_dependency,
)


def _make_engine() -> OrchestratorEngine:
    """创建引擎并注册 tia_multi_block_pipeline 工作流及全部 mock 工具。"""
    engine = OrchestratorEngine()
    register_tia_multi_block_pipeline_workflow(engine)

    engine.register_mocks({
        "tia-mcp.import_scl_file": lambda scl_code="", block_name="", replace=True: {
            "ok": True,
            "block_name": block_name,
        },
        "plc-mcp-bridge.plc_compile_project": lambda: {
            "ok": True,
            "success": True,
            "errors": 0,
        },
    })
    return engine


def _sample_blocks() -> list[dict]:
    """标准 3 块依赖场景: UDT -> DB -> FB"""
    return [
        {
            "type": "UDT",
            "name": "MotorParams",
            "scl_code": 'TYPE "MotorParams"\nSTRUCT\n  Speed : REAL;\n  Torque : REAL;\nEND_STRUCT\nEND_TYPE',
        },
        {
            "type": "DB",
            "name": "DB_Process",
            "scl_code": 'DATA_BLOCK "DB_Process"\nBEGIN\nEND_DATA_BLOCK',
        },
        {
            "type": "FB",
            "name": "MotorCtrl",
            "scl_code": 'FUNCTION_BLOCK "MotorCtrl"\nBEGIN\nEND_FUNCTION_BLOCK',
        },
    ]


# ============================================================================
# 注册测试
# ============================================================================


class TestRegistration:
    """工作流注册"""

    def test_workflow_registered(self):
        engine = OrchestratorEngine()
        register_tia_multi_block_pipeline_workflow(engine)
        assert "tia_multi_block_pipeline" in engine.list_workflows()

    def test_workflow_retrievable(self):
        engine = OrchestratorEngine()
        register_tia_multi_block_pipeline_workflow(engine)
        assert engine.get_workflow("tia_multi_block_pipeline") is not None


# ============================================================================
# 依赖排序测试
# ============================================================================


class TestSortBlocksByDependency:
    """_sort_blocks_by_dependency 函数"""

    def test_udt_before_db_before_fb(self):
        """UDT -> DB -> FB 正确顺序"""
        blocks = [
            {"type": "FB", "name": "MotorCtrl"},
            {"type": "DB", "name": "DB_Process"},
            {"type": "UDT", "name": "MotorParams"},
        ]
        sorted_blocks = _sort_blocks_by_dependency(blocks)
        types = [b["type"] for b in sorted_blocks]
        assert types == ["UDT", "DB", "FB"]

    def test_multiple_fc_fb_ob_same_priority(self):
        """FC/FB/OB 同优先级，保持原始相对顺序（稳定排序）"""
        blocks = [
            {"type": "FB", "name": "FB2"},
            {"type": "OB", "name": "OB1"},
            {"type": "FC", "name": "FC1"},
            {"type": "UDT", "name": "UDT1"},
        ]
        sorted_blocks = _sort_blocks_by_dependency(blocks)
        types = [b["type"] for b in sorted_blocks]
        assert types[0] == "UDT"
        # FC/FB/OB 顺序任意，但都在 UDT 之后
        assert set(types[1:]) == {"FC", "FB", "OB"}

    def test_db_after_udt(self):
        """DB 始终在 UDT 之后"""
        blocks = [
            {"type": "DB", "name": "DB1"},
            {"type": "UDT", "name": "UDT1"},
        ]
        sorted_blocks = _sort_blocks_by_dependency(blocks)
        types = [b["type"] for b in sorted_blocks]
        assert types == ["UDT", "DB"]

    def test_unknown_type_last(self):
        """未知类型排到最后"""
        blocks = [
            {"type": "UNKNOWN", "name": "X"},
            {"type": "FB", "name": "FB1"},
            {"type": "UDT", "name": "UDT1"},
        ]
        sorted_blocks = _sort_blocks_by_dependency(blocks)
        types = [b["type"] for b in sorted_blocks]
        assert types == ["UDT", "FB", "UNKNOWN"]

    def test_all_same_type_preserves_order(self):
        """同类型保持输入顺序（稳定排序）"""
        blocks = [
            {"type": "FB", "name": "FB_A"},
            {"type": "FB", "name": "FB_B"},
            {"type": "FB", "name": "FB_C"},
        ]
        sorted_blocks = _sort_blocks_by_dependency(blocks)
        names = [b["name"] for b in sorted_blocks]
        assert names == ["FB_A", "FB_B", "FB_C"]


# ============================================================================
# 3 块依赖场景通过
# ============================================================================


class TestThreeBlockScenario:
    """UDT -> DB -> FB 3 块依赖场景"""

    @pytest.mark.asyncio
    async def test_three_blocks_import_and_compile(self):
        """3 块全部导入并编译成功"""
        engine = _make_engine()
        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": _sample_blocks()},
        )
        assert result.ok is True
        # 步骤: 3 个 import + 1 个 compile = 4 步
        assert len(result.steps) == 4
        for step in result.steps:
            assert step.ok is True, f"步骤 {step.tool} 失败: {step.error}"

    @pytest.mark.asyncio
    async def test_imported_blocks_in_correct_order(self):
        """导入的块按 UDT->DB->FB 顺序执行"""
        engine = OrchestratorEngine()
        register_tia_multi_block_pipeline_workflow(engine)

        captured_blocks: list[str] = []

        def capture_import(scl_code="", block_name="", replace=True):
            captured_blocks.append(block_name)
            return {"ok": True, "block_name": block_name}

        engine.register_mocks({
            "tia-mcp.import_scl_file": capture_import,
            "plc-mcp-bridge.plc_compile_project": lambda: {"ok": True, "success": True, "errors": 0},
        })

        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": _sample_blocks()},
        )
        assert result.ok is True
        # 验证排序: UDT 先于 DB, DB 先于 FB
        assert captured_blocks == ["MotorParams", "DB_Process", "MotorCtrl"]

    @pytest.mark.asyncio
    async def test_all_steps_succeed_and_compile_ok(self):
        """所有步骤成功，最后一步是编译且成功"""
        engine = _make_engine()
        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": _sample_blocks()},
        )
        assert result.ok is True
        # 4 步全部成功
        assert len(result.steps) == 4
        # 最后一步是 compile
        compile_step = result.steps[-1]
        assert compile_step.tool == "plc-mcp-bridge.plc_compile_project"
        assert compile_step.ok is True
        assert compile_step.data["ok"] is True

    @pytest.mark.asyncio
    async def test_tools_executed_in_order(self):
        """验证工具调用顺序: 3个import + 1个compile"""
        engine = _make_engine()
        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": _sample_blocks()},
        )
        assert result.ok is True
        tools = [s.tool for s in result.steps]
        expected = [
            "tia-mcp.import_scl_file",
            "tia-mcp.import_scl_file",
            "tia-mcp.import_scl_file",
            "plc-mcp-bridge.plc_compile_project",
        ]
        assert tools == expected

    @pytest.mark.asyncio
    async def test_import_uses_replace_true(self):
        """验证 import 步骤使用 replace=True"""
        engine = OrchestratorEngine()
        register_tia_multi_block_pipeline_workflow(engine)

        def capture_import(scl_code="", block_name="", replace=True):
            return {
                "ok": True,
                "block_name": block_name,
                "replace_used": replace,
            }

        engine.register_mocks({
            "tia-mcp.import_scl_file": capture_import,
            "plc-mcp-bridge.plc_compile_project": lambda: {"ok": True, "success": True, "errors": 0},
        })

        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": _sample_blocks()},
        )
        assert result.ok is True
        for step in result.steps[:3]:
            assert step.data["replace_used"] is True


# ============================================================================
# 顺序错误时框架自动排序
# ============================================================================


class TestAutoSorting:
    """输入顺序错误时框架自动按依赖排序"""

    @pytest.mark.asyncio
    async def test_db_before_udt_still_works(self):
        """DB 在 UDT 之前输入 — 框架自动排序后 UDT 先导入"""
        blocks = [
            {"type": "DB", "name": "DB_Process", "scl_code": "DATA_BLOCK..."},
            {"type": "UDT", "name": "MotorParams", "scl_code": "TYPE MotorParams..."},
            {"type": "FB", "name": "MotorCtrl", "scl_code": "FUNCTION_BLOCK..."},
        ]
        engine = _make_engine()
        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": blocks},
        )
        assert result.ok is True
        assert len(result.steps) == 4
        # 验证 import 步骤的 data 中块顺序: UDT 在先
        import_steps = result.steps[:3]
        import_names = [s.data["block_name"] for s in import_steps]
        assert import_names == ["MotorParams", "DB_Process", "MotorCtrl"]

    @pytest.mark.asyncio
    async def test_fb_before_db_before_udt_still_works(self):
        """完全倒序输入 — 框架自动排序仍正确"""
        blocks = [
            {"type": "FB", "name": "FB1", "scl_code": "FB..."},
            {"type": "DB", "name": "DB1", "scl_code": "DB..."},
            {"type": "UDT", "name": "UDT1", "scl_code": "UDT..."},
        ]
        engine = _make_engine()
        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": blocks},
        )
        assert result.ok is True
        import_names = [s.data["block_name"] for s in result.steps[:3]]
        assert import_names == ["UDT1", "DB1", "FB1"]

    @pytest.mark.asyncio
    async def test_random_order_still_works(self):
        """随机顺序 — 排序后所有步骤成功"""
        blocks = [
            {"type": "FB", "name": "FB2", "scl_code": "FB2..."},
            {"type": "UDT", "name": "UDT1", "scl_code": "UDT1..."},
            {"type": "FB", "name": "FB1", "scl_code": "FB1..."},
            {"type": "DB", "name": "DB1", "scl_code": "DB1..."},
            {"type": "UDT", "name": "UDT2", "scl_code": "UDT2..."},
        ]
        engine = _make_engine()
        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": blocks},
        )
        assert result.ok is True
        assert len(result.steps) == 6  # 5 import + 1 compile

        # 验证排序: UDT 应该先于 DB, DB 应该先于 FB
        import_names = [s.data["block_name"] for s in result.steps[:5]]
        udt_positions = [i for i, n in enumerate(import_names) if n.startswith("UDT")]
        db_positions = [i for i, n in enumerate(import_names) if n.startswith("DB")]
        fb_positions = [i for i, n in enumerate(import_names) if n.startswith("FB")]
        assert all(p < min(fb_positions) for p in db_positions), "DB 应在 FB 之前"
        assert all(p < min(db_positions) for p in udt_positions), "UDT 应在 DB 之前"


# ============================================================================
# 导入失败时中止
# ============================================================================


class TestImportFailure:
    """导入失败时中止后续步骤"""

    @pytest.mark.asyncio
    async def test_first_import_fails_aborts(self):
        """第一个导入失败 — 不执行后续 import 和 compile"""
        engine = OrchestratorEngine()
        register_tia_multi_block_pipeline_workflow(engine)

        def failing_first_import(scl_code="", block_name="", replace=True):
            raise RuntimeError("导入 UDT 失败：网络错误")

        engine.register_mocks({
            "tia-mcp.import_scl_file": failing_first_import,
            "plc-mcp-bridge.plc_compile_project": lambda: {"ok": True, "success": True, "errors": 0},
        })

        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": _sample_blocks()},
        )
        assert result.ok is False
        # 只有 1 个步骤（失败的 import），异常被 catch 后工作流 return 了
        assert len(result.steps) == 1
        assert result.steps[0].ok is False
        assert "导入 UDT 失败" in result.steps[0].error

    @pytest.mark.asyncio
    async def test_second_import_fails_aborts(self):
        """第二个导入失败 — 已执行的 import 仍在，后续不执行"""
        engine = OrchestratorEngine()
        register_tia_multi_block_pipeline_workflow(engine)

        call_count = {"n": 0}

        def failing_second_import(scl_code="", block_name="", replace=True):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise RuntimeError(f"导入 {block_name} 失败")
            return {"ok": True, "block_name": block_name}

        engine.register_mocks({
            "tia-mcp.import_scl_file": failing_second_import,
            "plc-mcp-bridge.plc_compile_project": lambda: {"ok": True, "success": True, "errors": 0},
        })

        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": _sample_blocks()},
        )
        assert result.ok is False
        # 2 个步骤: 第 1 个成功, 第 2 个失败，第 3 个和 compile 未执行
        assert len(result.steps) == 2
        assert result.steps[0].ok is True
        assert result.steps[1].ok is False

    @pytest.mark.asyncio
    async def test_compile_fails_after_all_imports(self):
        """所有 import 成功后编译返回失败 — 步骤记录编译的失败结果"""
        engine = OrchestratorEngine()
        register_tia_multi_block_pipeline_workflow(engine)

        engine.register_mocks({
            "tia-mcp.import_scl_file": lambda scl_code="", block_name="", replace=True: {
                "ok": True, "block_name": block_name,
            },
            "plc-mcp-bridge.plc_compile_project": lambda: {
                "ok": False,
                "success": False,
                "errors": 3,
            },
        })

        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": _sample_blocks()},
        )
        # 3 个 import 都成功，compile 本身不抛异常但返回 ok=False
        # 工作流 catch 到 compile_ok 为 False 后 return error
        # 所以 steps 有 4 步(3 import + 1 compile)
        assert len(result.steps) == 4
        # 前 3 步 import 成功
        for s in result.steps[:3]:
            assert s.ok is True
        # compile 步骤 ok=True（工具没抛异常），但 data 里 ok=False
        compile_step = result.steps[3]
        assert compile_step.ok is True  # ctx.call_async 没抛异常
        assert compile_step.data["ok"] is False  # 编译本身失败了

    @pytest.mark.asyncio
    async def test_compile_throws_returns_error(self):
        """编译抛异常时中止"""
        engine = OrchestratorEngine()
        register_tia_multi_block_pipeline_workflow(engine)

        def compile_throws():
            raise RuntimeError("编译超时")

        engine.register_mocks({
            "tia-mcp.import_scl_file": lambda scl_code="", block_name="", replace=True: {
                "ok": True, "block_name": block_name,
            },
            "plc-mcp-bridge.plc_compile_project": compile_throws,
        })

        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": _sample_blocks()},
        )
        assert result.ok is False
        assert len(result.steps) == 4  # 3 import + 1 compile(throw)
        assert result.steps[3].ok is False
        assert "编译超时" in result.steps[3].error


# ============================================================================
# 空输入测试
# ============================================================================


class TestEmptyInput:
    """空输入和边界条件"""

    @pytest.mark.asyncio
    async def test_empty_blocks_raises(self):
        """空 blocks 列表抛出 ValueError"""
        engine = _make_engine()
        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={"blocks": []},
        )
        assert result.ok is False
        assert "不能为空" in result.error

    @pytest.mark.asyncio
    async def test_missing_name_returns_error(self):
        """缺少 name 字段 — 工作流提前 return error，无步骤记录"""
        engine = _make_engine()
        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={
                "blocks": [
                    {"type": "FB", "scl_code": "FB..."},  # 缺少 name
                ]
            },
        )
        # 工作流直接 return error，没调任何工具，步骤为空
        # WorkflowResult 无 .data 字段：验证通过 result.ok + 0 steps 确认提前返回
        assert result.ok is True  # 没抛异常
        assert len(result.steps) == 0  # 没有调用任何工具 = 提前返回了 error
        assert result.error == ""  # 没有 engine 层异常（不是 ValueError 之类的）

    @pytest.mark.asyncio
    async def test_missing_scl_code_returns_error(self):
        """缺少 scl_code 字段 — 工作流提前 return error，无步骤记录"""
        engine = _make_engine()
        result = await engine.run_async(
            "tia_multi_block_pipeline",
            input={
                "blocks": [
                    {"type": "FB", "name": "FB1"},  # 缺少 scl_code
                ]
            },
        )
        # 工作流直接 return error，没调任何工具，步骤为空
        assert result.ok is True  # 没抛异常
        assert len(result.steps) == 0  # 没有调用任何工具 = 提前返回了 error
        assert result.error == ""  # 没有 engine 层异常（不是 ValueError 之类的）
