"""MCP 工具函数单元测试"""
import json
import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _mock_tiaworker_ok(data: dict):
    """构造 TiaWorker 成功响应的 mock"""
    return MagicMock(
        stdout=json.dumps({"ok": True, "result": data, "error": None}),
        stderr="",
        returncode=0,
    )


def _mock_tiaworker_err(error: str):
    """构造 TiaWorker 失败响应的 mock"""
    return MagicMock(
        stdout=json.dumps({"ok": False, "result": None, "error": error}),
        stderr="",
        returncode=1,
    )


@pytest.fixture
def fake_project(tmp_path):
    """创建一个假项目文件用于测试"""
    project_file = tmp_path / "test.ap18"
    project_file.touch()
    fake_exe = tmp_path / "TiaWorker.exe"
    fake_exe.touch()
    with patch("_helpers.PROJECT_PATH", str(project_file)), \
         patch("_helpers.TIAWORKER_EXE", fake_exe):
        # 同步到各个 tools 模块
        import tools_blocks, tools_tags, tools_types, tools_project
        yield str(project_file)


# ── blocks 工具 ──

class TestBlockTools:
    @pytest.mark.asyncio
    async def test_list_blocks(self, fake_project):
        from tools_blocks import list_blocks
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({
            "count": 2,
            "blocks": [
                {"type": "FB", "number": 1, "name": "MotorCtrl", "language": "SCL"},
                {"type": "OB", "number": 1, "name": "Main", "language": "LAD"},
            ],
        })):
            result = await list_blocks()
            assert "PLC 块 (2)" in result
            assert "MotorCtrl" in result
            assert "Main" in result

    @pytest.mark.asyncio
    async def test_list_blocks_empty(self, fake_project):
        from tools_blocks import list_blocks
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({"count": 0, "blocks": []})):
            result = await list_blocks()
            assert "无 PLC 块" in result

    @pytest.mark.asyncio
    async def test_create_block(self, fake_project):
        from tools_blocks import create_block
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({
            "blockName": "TestFB",
            "number": 10,
        })):
            result = await create_block("TestFB", "FB", "SCL")
            assert "✅" in result
            assert "TestFB" in result

    @pytest.mark.asyncio
    async def test_delete_block(self, fake_project):
        from tools_blocks import delete_block
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({
            "deleted": "TestFB",
            "number": 10,
        })):
            result = await delete_block("TestFB")
            assert "✅" in result
            assert "TestFB" in result

    @pytest.mark.asyncio
    async def test_delete_block_not_found(self, fake_project):
        from tools_blocks import delete_block
        with patch("subprocess.run", return_value=_mock_tiaworker_err("Block 'X' not found")):
            result = await delete_block("X")
            assert "❌" in result

    @pytest.mark.asyncio
    async def test_compile_block(self, fake_project):
        from tools_blocks import compile_block
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({
            "success": True, "errors": 0, "warnings": 1,
        })):
            result = await compile_block("Main")
            assert "通过" in result
            assert "警告: 1" in result

    @pytest.mark.asyncio
    async def test_get_block_interface(self, fake_project):
        from tools_blocks import get_block_interface
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({
            "blockName": "MotorCtrl",
            "sections": [
                {"section": "Input", "members": [{"name": "bStart", "dataType": "Bool"}]},
                {"section": "Output", "members": [{"name": "bRunning", "dataType": "Bool"}]},
            ],
        })):
            result = await get_block_interface("MotorCtrl")
            assert "MotorCtrl" in result
            assert "bStart" in result
            assert "bRunning" in result


# ── tags 工具 ──

class TestTagTools:
    @pytest.mark.asyncio
    async def test_list_tag_tables(self, fake_project):
        from tools_tags import list_tag_tables
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({
            "tables": [{"name": "Default tag table", "tagCount": 5}],
        })):
            result = await list_tag_tables()
            assert "Default tag table" in result
            assert "5 个标签" in result

    @pytest.mark.asyncio
    async def test_add_tag(self, fake_project):
        from tools_tags import add_tag
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({
            "tagName": "Motor1", "dataType": "Bool", "address": "%M0.0",
        })):
            result = await add_tag("Default tag table", "Motor1", "Bool", "%M0.0")
            assert "✅" in result
            assert "Motor1" in result

    @pytest.mark.asyncio
    async def test_search_tags(self, fake_project):
        from tools_tags import search_tags
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({
            "query": "Motor",
            "results": [
                {"table": "Default", "name": "Motor1", "dataType": "Bool", "address": "%M0.0"},
            ],
        })):
            result = await search_tags("Motor")
            assert "Motor1" in result
            assert "1 个结果" in result

    @pytest.mark.asyncio
    async def test_search_tags_empty(self, fake_project):
        from tools_tags import search_tags
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({
            "query": "xyz", "results": [],
        })):
            result = await search_tags("xyz")
            assert "未找到" in result


# ── project 工具 ──

class TestProjectTools:
    @pytest.mark.asyncio
    async def test_compile_project(self, fake_project):
        from tools_project import compile_project
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({
            "errors": 0, "warnings": 2,
        })):
            result = await compile_project()
            assert "✅" in result

    @pytest.mark.asyncio
    async def test_get_project_info(self, fake_project):
        from tools_project import get_project_info
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({
            "name": "TestProject", "path": "C:\\test", "deviceCount": 1,
        })):
            result = await get_project_info()
            assert "TestProject" in result

    @pytest.mark.asyncio
    async def test_check_consistency(self, fake_project):
        from tools_project import check_consistency
        with patch("subprocess.run", return_value=_mock_tiaworker_ok({
            "total": 3, "consistent": 2,
            "blocks": [
                {"name": "Main", "number": 1, "isConsistent": True},
                {"name": "FB1", "number": 2, "isConsistent": True},
                {"name": "FB2", "number": 3, "isConsistent": False},
            ],
        })):
            result = await check_consistency()
            assert "2/3" in result
            assert "FB2" in result


# ── plcsim 工具 ──

class TestPlcsimTools:
    @pytest.mark.asyncio
    async def test_list_instances(self):
        from tools_plcsim import list_instances
        with patch("tools_plcsim._run_python", return_value={
            "success": True,
            "output": "factoryio  RUN  192.168.0.1",
        }):
            result = await list_instances()
            assert "factoryio" in result

    @pytest.mark.asyncio
    async def test_restore_no_golden(self):
        from tools_plcsim import restore_from_golden
        with patch("tools_plcsim.GOLDEN_ZIP", ""), \
             patch("tools_plcsim.STORAGE_PATH", ""):
            result = await restore_from_golden()
            assert "❌" in result
            assert "配置缺失" in result


# ── 无项目路径场景 ──

class TestNoProject:
    @pytest.mark.asyncio
    async def test_blocks_no_project(self):
        from tools_blocks import list_blocks
        with patch("_helpers.PROJECT_PATH", ""):
            result = await list_blocks()
            assert "不存在" in result

    @pytest.mark.asyncio
    async def test_tags_no_project(self):
        from tools_tags import list_tag_tables
        with patch("_helpers.PROJECT_PATH", ""):
            result = await list_tag_tables()
            assert "不存在" in result

    @pytest.mark.asyncio
    async def test_project_no_project(self):
        from tools_project import compile_project
        with patch("_helpers.PROJECT_PATH", ""):
            result = await compile_project()
            assert "不存在" in result
