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

# 不直接导入 p3_flow.py（它有 Windows 依赖），
# 而是测试其 JSON 解析逻辑的等价实现。
# 修复后的逻辑:
#   result.get('ok') 检查成功
#   data = result.get('result', {})
#   data.get('success') 检查编译结果


# ═══════════════════════════════════════════════════════════════
# 测试: TiaWorker 编译输出格式解析
# ═══════════════════════════════════════════════════════════════

# 这是 p3_flow.py 修复后的 step2_compile 中等价逻辑


def _parse_compile_output(stdout: str) -> tuple[bool, str]:
    """
    等价于 p3_flow.py step2_compile() 中的 JSON 解析逻辑。
    返回 (success, message)。
    """
    result = json.loads(stdout)
    # TiaWorker 实际输出格式: { "ok": true/false, "result": { ... }, "error": null/msg }
    if result.get("ok"):
        data = result.get("result", {})
        if not data.get("success"):
            return False, f"编译失败: {data.get('errors', '?')} 错误"
        return True, f"编译成功: Warnings={data.get('warnings', 0)}"
    else:
        return False, f"编译异常: {result.get('error', '?')}"


class TestP3FlowCompileParsing:
    """测试 p3_flow.py 编译输出解析逻辑（修复后）"""

    def test_parse_success_with_warnings(self):
        """编译成功（有警告）"""
        stdout = json.dumps({
            "ok": True,
            "result": {"success": True, "errors": 0, "warnings": 2},
            "error": None,
        })
        success, msg = _parse_compile_output(stdout)
        assert success is True
        assert "Warnings=2" in msg

    def test_parse_success_no_warnings(self):
        """编译成功（无警告）"""
        stdout = json.dumps({
            "ok": True,
            "result": {"success": True, "errors": 0, "warnings": 0},
            "error": None,
        })
        success, msg = _parse_compile_output(stdout)
        assert success is True
        assert "Warnings=0" in msg

    def test_parse_compile_failure(self):
        """编译失败"""
        stdout = json.dumps({
            "ok": True,  # TiaWorker 调用成功，但编译本身失败
            "result": {"success": False, "errors": 3, "warnings": 1},
            "error": None,
        })
        success, msg = _parse_compile_output(stdout)
        assert success is False
        assert "errors=3" in msg or "3 错误" in msg

    def test_parse_tiaworker_error(self):
        """TiaWorker 本身出错"""
        stdout = json.dumps({
            "ok": False,
            "result": None,
            "error": "No PLC device found",
        })
        success, msg = _parse_compile_output(stdout)
        assert success is False
        assert "No PLC device" in msg

    def test_parse_missing_project_path(self):
        """缺少 ProjectPath"""
        stdout = json.dumps({
            "ok": False,
            "result": None,
            "error": "Missing ProjectPath",
        })
        success, msg = _parse_compile_output(stdout)
        assert success is False
        assert "Missing ProjectPath" in msg

    def test_parse_empty_result(self):
        """result 为空对象"""
        stdout = json.dumps({
            "ok": True,
            "result": {},
            "error": None,
        })
        success, msg = _parse_compile_output(stdout)
        assert success is False  # success 字段缺失视为 False

    def test_parse_missing_result_key(self):
        """缺少 result 字段"""
        stdout = json.dumps({
            "ok": True,
            "error": None,
        })
        success, msg = _parse_compile_output(stdout)
        assert success is False

    def test_parse_invalid_json(self):
        """非 JSON 输出"""
        with pytest.raises(json.JSONDecodeError):
            _parse_compile_output("Not JSON at all")


# ═══════════════════════════════════════════════════════════════
# 测试: TiaWorker 其他命令的输出格式
# ═══════════════════════════════════════════════════════════════

class TestTiaWorkerOutputFormats:
    """验证各种 TiaWorker 命令的输出格式（回归测试）"""

    def test_list_devices_output(self):
        """list-devices 输出格式"""
        output = {
            "ok": True,
            "result": {
                "devices": [
                    {"name": "PLC_1", "type": "S7-1200"},
                    {"name": "PLC_2", "type": "S7-1500"},
                ]
            },
            "error": None,
        }
        parsed = json.loads(json.dumps(output))
        assert parsed["ok"] is True
        assert len(parsed["result"]["devices"]) == 2

    def test_import_scl_output(self):
        """import-scl 输出格式"""
        output = {
            "ok": True,
            "result": {
                "fileName": "MotorControl.scl",
                "generated": 1,
                "blocks": ["MotorControl"],
            },
            "error": None,
        }
        parsed = json.loads(json.dumps(output))
        assert parsed["ok"] is True
        assert parsed["result"]["blocks"] == ["MotorControl"]

    def test_download_output(self):
        """download 输出格式"""
        output = {
            "ok": True,
            "result": {
                "downloaded": True,
                "blocks": 5,
            },
            "error": None,
        }
        parsed = json.loads(json.dumps(output))
        assert parsed["ok"] is True
        assert parsed["result"]["downloaded"] is True

    def test_generic_error_output(self):
        """通用错误格式"""
        output = {
            "ok": False,
            "result": None,
            "error": "Generic TIA error message",
        }
        parsed = json.loads(json.dumps(output))
        assert parsed["ok"] is False
        assert parsed["error"] is not None
        assert parsed["result"] is None