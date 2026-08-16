"""robot-mcp write_io 审计前置门（fail-closed）测试。

真实后端（snap7/opcua）写入前必须先成功写入 begin_control_operation
控制意图审计；审计链不可用时拒绝执行写入（对齐 opcua/modbus 兄弟服务器）。
模拟后端是离线测试兼容路径，不设此门。
"""

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def robot_server():
    spec = importlib.util.spec_from_file_location(
        "robot_audit_gate_server", PROJECT_ROOT / "mcp-servers" / "robot-mcp" / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["robot_audit_gate_server"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def snap7_backend(robot_server, monkeypatch):
    """构造已连接的 snap7 后端（急停位健康），不触发任何真实网络连接。"""
    backend = robot_server.RobotBackend()

    async def _connected():
        return True

    monkeypatch.setattr(backend, "ensure_connected", _connected)
    backend._backend_type = "snap7"
    backend._snap_client = MagicMock()
    # 输入区读回急停位（I0.8 → byte1 bit0）为健康；输出区读回全 0
    backend._snap_client.read_area.side_effect = (
        lambda area, db, start, size: b"\x01" if area == 0x81 else b"\x00"
    )
    return backend


def test_real_backend_write_blocked_when_audit_unavailable(robot_server, snap7_backend, monkeypatch):
    from mcp_common.audit import AuditStorageError

    broken = MagicMock()
    broken.begin_control_operation.side_effect = AuditStorageError("audit storage unavailable")
    monkeypatch.setattr(robot_server, "_robot_audit", broken)

    result = asyncio.run(snap7_backend.write_io("grab", True))
    assert result["status"] == "error"
    assert "审计" in result["error"]
    snap7_backend._snap_client.write_area.assert_not_called()


def test_real_backend_write_proceeds_after_audit_intent(robot_server, snap7_backend, monkeypatch):
    audit = MagicMock()
    monkeypatch.setattr(robot_server, "_robot_audit", audit)

    result = asyncio.run(snap7_backend.write_io("grab", True))
    assert result["status"] == "ok"
    audit.begin_control_operation.assert_called_once()
    snap7_backend._snap_client.write_area.assert_called_once()


def test_simulated_backend_write_not_gated_by_audit(robot_server, snap7_backend, monkeypatch):
    from mcp_common.audit import AuditStorageError

    snap7_backend._backend_type = "simulated"
    broken = MagicMock()
    broken.begin_control_operation.side_effect = AuditStorageError("audit storage unavailable")
    monkeypatch.setattr(robot_server, "_robot_audit", broken)

    result = asyncio.run(snap7_backend.write_io("grab", True))
    # 模拟路径是离线测试兼容路径，不走审计前置门
    assert result["status"] == "ok"
