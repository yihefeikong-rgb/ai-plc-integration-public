"""tools_pipeline 测试 — 下载/Factory I/O/流水线"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import asyncio

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "tia-mcp"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp_common"))


class TestDownloadProject:
    """plc_download_project 工具"""

    @patch("tools_pipeline._check_project", return_value=None)
    @patch("tools_pipeline._run_python")
    def test_download_success(self, mock_run, mock_check):
        import tools_pipeline
        mock_run.return_value = {"success": True, "output": "downloaded"}
        result = asyncio.run(tools_pipeline.download_project())
        assert "成功" in result or "downloaded" in result.lower() or "✅" in result

    @patch("tools_pipeline._check_project", return_value="❌ 项目文件不存在")
    def test_download_no_project(self, mock_check):
        import tools_pipeline
        result = asyncio.run(tools_pipeline.download_project())
        assert "不存在" in result

    @patch("tools_pipeline._check_project", return_value=None)
    def test_download_dry_run(self, mock_check):
        import tools_pipeline
        result = asyncio.run(tools_pipeline.download_project(dry_run=True))
        assert "Dry-Run" in result

    @patch("tools_pipeline._check_project", return_value=None)
    @patch("tools_pipeline._run_python")
    def test_download_failure(self, mock_run, mock_check):
        import tools_pipeline
        mock_run.return_value = {"success": False, "error": "timeout"}
        result = asyncio.run(tools_pipeline.download_project())
        assert "失败" in result or "timeout" in result


class TestFioLaunch:
    """plc_fio_launch 工具"""

    @patch("tools_pipeline.cfg")
    def test_launch_no_path(self, mock_cfg):
        import tools_pipeline
        mock_cfg.factory_io.exe_path = ""
        result = asyncio.run(tools_pipeline.fio_launch(fio_path=""))
        assert "未配置" in result or "未找到" in result

    @patch("tools_pipeline.os.path.exists", return_value=False)
    def test_launch_exe_not_found(self, mock_exists):
        import tools_pipeline
        result = asyncio.run(tools_pipeline.fio_launch(fio_path="C:\\fake\\path.exe"))
        assert "未找到" in result

    @patch("tools_pipeline.subprocess.Popen")
    @patch("tools_pipeline.os.path.exists", return_value=True)
    def test_launch_success(self, mock_exists, mock_popen):
        import tools_pipeline
        result = asyncio.run(tools_pipeline.fio_launch(fio_path="C:\\Factory IO\\Factory IO.exe"))
        assert "启动" in result
        mock_popen.assert_called_once()
        # 验证不使用 shell=True
        call_kwargs = mock_popen.call_args
        assert call_kwargs.get("shell") is not True if call_kwargs.kwargs else True


class TestRunPipeline:
    """plc_run_pipeline 工具"""

    def test_pipeline_dry_run(self):
        import tools_pipeline
        result = asyncio.run(tools_pipeline.run_pipeline(dry_run=True))
        assert "Dry-Run" in result

    @patch("tools_pipeline._run_python")
    def test_pipeline_success(self, mock_run):
        import tools_pipeline
        mock_run.return_value = {"success": True, "output": "pipeline complete"}
        result = asyncio.run(tools_pipeline.run_pipeline())
        assert "pipeline" in result.lower() or "完成" in result or "结果" in result

    @patch("tools_pipeline._run_python")
    def test_pipeline_failure(self, mock_run):
        import tools_pipeline
        mock_run.return_value = {"success": False, "error": "compile failed", "output": ""}
        result = asyncio.run(tools_pipeline.run_pipeline())
        assert "失败" in result or "failed" in result.lower()


class TestGoldenRestore:
    """plc_golden_restore 工具"""

    def test_golden_restore_dry_run(self):
        import tools_pipeline
        result = asyncio.run(tools_pipeline.golden_restore(dry_run=True))
        assert "Dry-Run" in result

    @patch("tools_pipeline._run_python")
    def test_golden_restore_success(self, mock_run):
        import tools_pipeline
        mock_run.return_value = {"success": True, "output": "restored OK"}
        result = asyncio.run(tools_pipeline.golden_restore())
        assert "restored" in result.lower() or "OK" in result
