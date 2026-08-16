"""
p3_flow.py 编译输出解析测试

验证 TS002 修复：p3_flow.py 现在正确解析 TiaWorker 的
{ ok, result, error } 格式，而不是错误的 { status, data } 格式。
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 直接导入并调用 scripts/p3_flow.py 的真实解析逻辑（mock 掉 TiaWorker 子进程
# 与临时文件），防止 p3_flow.py 回退到旧 {status, data} 解析时本测试仍全绿。


# ═══════════════════════════════════════════════════════════════
# 测试: TiaWorker 编译输出格式解析（真实 step2_compile）
# ═══════════════════════════════════════════════════════════════

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_P3_FLOW_IMPORT_ERROR = None
try:
    import p3_flow
except Exception as exc:  # 环境缺依赖（如 config_loader/yaml）时明确跳过，不静默误报
    p3_flow = None
    _P3_FLOW_IMPORT_ERROR = exc

_P3_FLOW_AVAILABLE = p3_flow is not None
pytestmark = pytest.mark.skipif(
    not _P3_FLOW_AVAILABLE,
    reason=f"scripts/p3_flow.py 无法导入，跳过真实解析测试: {_P3_FLOW_IMPORT_ERROR}",
)


def _run_real_compile(stdout_text: str) -> tuple[bool, str]:
    """
    调用真实的 p3_flow.step2_compile()，返回 (success, 最后一条日志消息)。
    不启动真实 TiaWorker.exe，也不读写控制目标。
    """
    logs: list[str] = []

    def _fake_log(msg: str, l: str = "info") -> None:
        logs.append(f"{l}:{msg}")

    with patch.object(p3_flow, "log", side_effect=_fake_log), \
         patch.object(p3_flow, "sep", return_value=None), \
         patch.object(p3_flow.os.path, "exists", return_value=True), \
         patch.object(p3_flow.subprocess, "run") as mock_run, \
         patch.object(p3_flow.tempfile, "NamedTemporaryFile") as mock_tmp:

        mock_run.return_value.stdout = stdout_text
        mock_tmp.return_value.name = "compile_input.json"
        success = p3_flow.step2_compile()

    return success, (logs[-1] if logs else "")


class TestP3FlowCompileParsing:
    """测试 p3_flow.py 编译输出解析逻辑（真实 step2_compile，mock 子进程）"""

    def test_parse_success_with_warnings(self):
        """编译成功（有警告）"""
        success, msg = _run_real_compile(json.dumps({
            "ok": True,
            "result": {"success": True, "errors": 0, "warnings": 2},
            "error": None,
        }))
        assert success is True
        assert "Warnings=2" in msg

    def test_parse_success_no_warnings(self):
        """编译成功（无警告）"""
        success, msg = _run_real_compile(json.dumps({
            "ok": True,
            "result": {"success": True, "errors": 0, "warnings": 0},
            "error": None,
        }))
        assert success is True
        assert "Warnings=0" in msg

    def test_parse_compile_failure(self):
        """编译失败"""
        success, msg = _run_real_compile(json.dumps({
            "ok": True,  # TiaWorker 调用成功，但编译本身失败
            "result": {"success": False, "errors": 3, "warnings": 1},
            "error": None,
        }))
        assert success is False
        assert "编译失败" in msg
        assert "3 错误" in msg

    def test_parse_tiaworker_error(self):
        """TiaWorker 本身出错"""
        success, msg = _run_real_compile(json.dumps({
            "ok": False,
            "result": None,
            "error": "No PLC device found",
        }))
        assert success is False
        assert "编译异常" in msg
        assert "No PLC device" in msg

    def test_parse_missing_project_path(self):
        """缺少 ProjectPath"""
        success, msg = _run_real_compile(json.dumps({
            "ok": False,
            "result": None,
            "error": "Missing ProjectPath",
        }))
        assert success is False
        assert "Missing ProjectPath" in msg

    def test_parse_empty_result(self):
        """result 为空对象（success 字段缺失视为失败）"""
        success, msg = _run_real_compile(json.dumps({
            "ok": True,
            "result": {},
            "error": None,
        }))
        assert success is False

    def test_parse_missing_result_key(self):
        """缺少 result 字段"""
        success, msg = _run_real_compile(json.dumps({
            "ok": True,
            "error": None,
        }))
        assert success is False

    def test_parse_invalid_json_fails_closed(self):
        """非 JSON 输出：真实实现 fail-closed 返回 False，不抛异常"""
        success, msg = _run_real_compile("Not JSON at all")
        assert success is False
        assert "编译输出解析失败" in msg

    def test_rejects_legacy_status_data_format(self):
        """回归防护：旧 {status, data} 格式必须被判为失败"""
        success, msg = _run_real_compile(json.dumps({
            "status": "success",
            "data": {"success": True},
        }))
        assert success is False
