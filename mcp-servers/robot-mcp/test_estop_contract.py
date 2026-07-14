import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


def load_robot_server():
    path = Path(__file__).with_name("server.py")
    spec = importlib.util.spec_from_file_location("robot_estop_server", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_estop_contract_fails_closed_and_requires_reconfirmation(monkeypatch):
    module = load_robot_server()
    monkeypatch.setattr(module, "BACKEND", "simulated")
    backend = module.RobotBackend()

    backend._sim_state["sensor_estop"] = True
    assert (await backend.write_io("arm_move_x", True))["status"] == "ok"

    backend._sim_state["sensor_estop"] = False
    blocked = await backend.write_io("arm_move_x", True)
    assert blocked["status"] == "error"
    assert "安全回路" in blocked["error"]

    backend._sim_state["sensor_estop"] = True
    needs_reconfirmation = await backend.write_io("arm_move_x", True)
    assert needs_reconfirmation["status"] == "error"
    assert "重新确认" in needs_reconfirmation["error"]

    assert (await backend.confirm_estop_recovery())["status"] == "ok"
    assert (await backend.write_io("arm_move_x", True))["status"] == "ok"

    monkeypatch.setattr(backend, "read_io", AsyncMock(return_value=None))
    unknown = await backend.write_io("arm_move_x", True)
    assert unknown["status"] == "error"
    assert "安全回路" in unknown["error"]
