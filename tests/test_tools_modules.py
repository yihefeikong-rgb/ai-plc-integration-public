"""tools_diagnostics / tools_hardware / tools_export / tools_types 测试

这些模块都通过 _run_tiaworker 调用子进程，测试验证:
- 成功路径格式化输出
- 失败路径错误处理
- dry_run/preview 模式
- _check_project 拦截
"""
import sys
from pathlib import Path
from unittest.mock import patch
import pytest
import asyncio

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "tia-mcp"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp_common"))


# ═══ tools_diagnostics ═══

class TestDiagnostics:
    """tools_diagnostics 诊断工具"""

    @patch("tools_diagnostics._check_project", return_value=None)
    @patch("tools_diagnostics._run_tiaworker")
    def test_get_plc_status_success(self, mock_tia, mock_check):
        import tools_diagnostics
        mock_tia.return_value = {
            "success": True,
            "data": {"device": "PLC_1", "status": "RUN", "online": True}
        }
        result = asyncio.run(tools_diagnostics.get_plc_status())
        assert "RUN" in result
        assert "PLC_1" in result

    @patch("tools_diagnostics._check_project", return_value=None)
    @patch("tools_diagnostics._run_tiaworker")
    def test_get_plc_status_failure(self, mock_tia, mock_check):
        import tools_diagnostics
        mock_tia.return_value = {"success": False, "error": "连接超时"}
        result = asyncio.run(tools_diagnostics.get_plc_status())
        assert "失败" in result or "超时" in result

    @patch("tools_diagnostics._check_project", return_value="❌ 项目文件不存在")
    def test_no_project(self, mock_check):
        import tools_diagnostics
        result = asyncio.run(tools_diagnostics.get_plc_status())
        assert "不存在" in result

    @patch("tools_diagnostics._check_project", return_value=None)
    def test_go_online_dry_run(self, mock_check):
        import tools_diagnostics
        result = asyncio.run(tools_diagnostics.go_online(dry_run=True))
        assert "Dry-Run" in result

    @patch("tools_diagnostics._check_project", return_value=None)
    def test_go_offline_dry_run(self, mock_check):
        import tools_diagnostics
        result = asyncio.run(tools_diagnostics.go_offline(dry_run=True))
        assert "Dry-Run" in result


# ═══ tools_hardware ═══

class TestHardware:
    """tools_hardware 硬件配置工具"""

    @patch("tools_hardware._check_project", return_value=None)
    @patch("tools_hardware._run_tiaworker")
    def test_get_device_config_success(self, mock_tia, mock_check):
        import tools_hardware
        mock_tia.return_value = {
            "success": True,
            "data": {
                "deviceCount": 1,
                "devices": [{"name": "PLC_1", "type": "S7-1500", "items": []}]
            }
        }
        result = asyncio.run(tools_hardware.get_device_config())
        assert "PLC_1" in result
        assert "S7-1500" in result

    @patch("tools_hardware._check_project", return_value=None)
    @patch("tools_hardware._run_tiaworker")
    def test_get_device_config_empty(self, mock_tia, mock_check):
        import tools_hardware
        mock_tia.return_value = {"success": True, "data": {"devices": []}}
        result = asyncio.run(tools_hardware.get_device_config())
        assert "无硬件设备" in result

    @patch("tools_hardware._check_project", return_value=None)
    @patch("tools_hardware._run_tiaworker")
    def test_get_rack_slot_success(self, mock_tia, mock_check):
        import tools_hardware
        mock_tia.return_value = {
            "success": True,
            "data": {
                "deviceCount": 1,
                "devices": [{"device": "PLC_1", "slots": [{"type": "CPU", "name": "CPU 1511", "depth": 1}]}]
            }
        }
        result = asyncio.run(tools_hardware.get_rack_slot())
        assert "PLC_1" in result
        assert "CPU" in result


# ═══ tools_export ═══

class TestExport:
    """tools_export CSV 导出工具"""

    @patch("tools_export._check_project", return_value=None)
    @patch("tools_export._run_tiaworker")
    def test_export_tags_success(self, mock_tia, mock_check):
        import tools_export
        mock_tia.return_value = {
            "success": True,
            "data": {"count": 15, "file": "tag_export.csv"}
        }
        result = asyncio.run(tools_export.export_tags_csv())
        assert "15" in result
        assert "✅" in result

    @patch("tools_export._check_project", return_value=None)
    @patch("tools_export._run_tiaworker")
    def test_export_tags_failure(self, mock_tia, mock_check):
        import tools_export
        mock_tia.return_value = {"success": False, "error": "无标签表"}
        result = asyncio.run(tools_export.export_tags_csv())
        assert "失败" in result or "无标签" in result

    @patch("tools_export._check_project", return_value=None)
    def test_export_dry_run(self, mock_check):
        import tools_export
        result = asyncio.run(tools_export.export_tags_csv(dry_run=True))
        assert "Dry-Run" in result


# ═══ tools_types ═══

class TestTypes:
    """tools_types UDT/Watch 表管理"""

    @patch("tools_types._check_project", return_value=None)
    @patch("tools_types._run_tiaworker")
    def test_create_udt_success(self, mock_tia, mock_check):
        import tools_types
        mock_tia.return_value = {"success": True, "data": {}}
        result = asyncio.run(tools_types.create_udt("MyType"))
        assert "✅" in result
        assert "MyType" in result

    @patch("tools_types._check_project", return_value=None)
    @patch("tools_types._run_tiaworker")
    def test_create_udt_failure(self, mock_tia, mock_check):
        import tools_types
        mock_tia.return_value = {"success": False, "error": "已存在"}
        result = asyncio.run(tools_types.create_udt("MyType"))
        assert "失败" in result or "已存在" in result

    @patch("tools_types._check_project", return_value=None)
    def test_create_udt_dry_run(self, mock_check):
        import tools_types
        result = asyncio.run(tools_types.create_udt("MyType", dry_run=True))
        assert "Dry-Run" in result

    @patch("tools_types._check_project", return_value=None)
    @patch("tools_types._run_tiaworker")
    def test_delete_udt_success(self, mock_tia, mock_check):
        import tools_types
        mock_tia.return_value = {"success": True, "data": {"deleted": "MyType"}}
        result = asyncio.run(tools_types.delete_udt("MyType"))
        assert "✅" in result

    @patch("tools_types._check_project", return_value=None)
    def test_delete_udt_preview(self, mock_check):
        import tools_types
        result = asyncio.run(tools_types.delete_udt("MyType", preview=True))
        assert "预览" in result or "Token" in result
