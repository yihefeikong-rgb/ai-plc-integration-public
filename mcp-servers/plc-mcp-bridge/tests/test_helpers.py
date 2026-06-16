"""_helpers 模块单元测试"""
import json
import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# 确保能导入被测模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestFormatResult:
    def test_success_no_data(self):
        from _helpers import _format_result
        assert _format_result(True) == "✅ 成功"

    def test_success_with_data(self):
        from _helpers import _format_result
        result = _format_result(True, data={"key": "value"})
        assert "✅ 成功" in result
        assert '"key": "value"' in result

    def test_failure(self):
        from _helpers import _format_result
        result = _format_result(False, error="something broke")
        assert "❌ 失败" in result
        assert "something broke" in result


class TestCheckProject:
    def test_empty_path(self):
        from _helpers import _check_project
        with patch("_helpers.PROJECT_PATH", ""):
            result = _check_project()
            assert result is not None
            assert "不存在" in result

    def test_nonexistent_path(self):
        from _helpers import _check_project
        with patch("_helpers.PROJECT_PATH", "/nonexistent/path.ap18"):
            result = _check_project()
            assert result is not None
            assert "不存在" in result

    def test_existing_path(self, tmp_path):
        from _helpers import _check_project
        fake_project = tmp_path / "test.ap18"
        fake_project.touch()
        with patch("_helpers.PROJECT_PATH", str(fake_project)):
            result = _check_project()
            assert result is None


class TestRunPython:
    def test_success_json_output(self):
        from _helpers import _run_python
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout='{"success": true, "data": "test"}',
                stderr="",
                returncode=0,
            )
            result = _run_python(Path("test.py"), [])
            assert result["success"] is True
            assert result["data"] == "test"

    def test_success_non_json(self):
        from _helpers import _run_python
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="plain text output",
                stderr="",
                returncode=0,
            )
            result = _run_python(Path("test.py"), [])
            assert result["success"] is True
            assert result["output"] == "plain text output"

    def test_failure(self):
        from _helpers import _run_python
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                stderr="error msg",
                returncode=1,
            )
            result = _run_python(Path("test.py"), [])
            assert result["success"] is False

    def test_timeout(self):
        from _helpers import _run_python
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            result = _run_python(Path("test.py"), [], timeout=5)
            assert result["success"] is False
            assert "超时" in result["error"]

    def test_exception(self):
        from _helpers import _run_python
        with patch("subprocess.run", side_effect=OSError("file not found")):
            result = _run_python(Path("test.py"), [])
            assert result["success"] is False
            assert "file not found" in result["error"]


class TestRunTiaworker:
    def test_tiaworker_not_found(self):
        from _helpers import _run_tiaworker
        with patch("_helpers.TIAWORKER_EXE", Path("/nonexistent/TiaWorker.exe")):
            result = _run_tiaworker("test", {})
            assert result["success"] is False
            assert "未编译" in result["error"]

    def test_success(self, tmp_path):
        from _helpers import _run_tiaworker
        fake_exe = tmp_path / "TiaWorker.exe"
        fake_exe.touch()
        with patch("_helpers.TIAWORKER_EXE", fake_exe):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=json.dumps({"ok": True, "result": {"count": 5}, "error": None}),
                    stderr="",
                    returncode=0,
                )
                result = _run_tiaworker("list-blocks", {"ProjectPath": "test"})
                assert result["success"] is True
                assert result["data"]["count"] == 5

    def test_tiaworker_error(self, tmp_path):
        from _helpers import _run_tiaworker
        fake_exe = tmp_path / "TiaWorker.exe"
        fake_exe.touch()
        with patch("_helpers.TIAWORKER_EXE", fake_exe):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=json.dumps({"ok": False, "result": None, "error": "block not found"}),
                    stderr="",
                    returncode=1,
                )
                result = _run_tiaworker("delete-block", {"BlockName": "x"})
                assert result["success"] is False
                assert "block not found" in result["error"]

    def test_no_output(self, tmp_path):
        from _helpers import _run_tiaworker
        fake_exe = tmp_path / "TiaWorker.exe"
        fake_exe.touch()
        with patch("_helpers.TIAWORKER_EXE", fake_exe):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
                result = _run_tiaworker("test", {})
                assert result["success"] is False
                assert "无输出" in result["error"]

    def test_timeout(self, tmp_path):
        from _helpers import _run_tiaworker
        import subprocess
        fake_exe = tmp_path / "TiaWorker.exe"
        fake_exe.touch()
        with patch("_helpers.TIAWORKER_EXE", fake_exe):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
                result = _run_tiaworker("test", {}, timeout=10)
                assert result["success"] is False
                assert "超时" in result["error"]
