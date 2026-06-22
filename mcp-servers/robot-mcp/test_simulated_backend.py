"""
TS013 — RobotBackend 模拟后端模式测试

测试 simulated 模式下:
  - 连接成功
  - 读取默认值
  - 写入 + 读取
  - 联动逻辑（grab → sensor_item_detected, arm_move_x → sensor_moving_x 等）
  - 急停状态模拟
  - read_all_inputs 在模拟模式下的行为
"""

import asyncio
import pytest
import sys
from pathlib import Path

# 确保可以导入 server 模块
sys.path.insert(0, str(Path(__file__).parent))

import server
from server import RobotBackend, IO_MAP


@pytest.fixture
def sim_backend(monkeypatch):
    """创建一个 simulated 模式的 RobotBackend 实例"""
    monkeypatch.setattr(server, "BACKEND", "simulated")
    backend = RobotBackend()
    # 连接模拟后端
    asyncio.get_event_loop().run_until_complete(backend.connect_simulated())
    return backend


class TestSimulatedConnect:
    """测试 simulated 连接"""

    def test_connect_simulated(self, monkeypatch):
        monkeypatch.setattr(server, "BACKEND", "simulated")
        backend = RobotBackend()
        result = asyncio.get_event_loop().run_until_complete(backend.connect_simulated())
        assert result is True
        assert backend.backend_type == "simulated"

    def test_ensure_connected_simulated(self, sim_backend):
        result = asyncio.get_event_loop().run_until_complete(sim_backend.ensure_connected())
        assert result is True


class TestSimulatedReadWrite:
    """测试 simulated 读写"""

    def test_read_default_values(self, sim_backend):
        """所有传感器默认值为 False"""
        for name in IO_MAP:
            if name.startswith("sensor_"):
                val = asyncio.get_event_loop().run_until_complete(sim_backend.read_io(name))
                assert val is False, f"{name} 默认值应为 False"

    def test_write_then_read(self, sim_backend):
        """写入后读取应返回写入值"""
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("conveyor_entry", True))
        val = asyncio.get_event_loop().run_until_complete(sim_backend.read_io("conveyor_entry"))
        assert val is True

        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("conveyor_entry", False))
        val = asyncio.get_event_loop().run_until_complete(sim_backend.read_io("conveyor_entry"))
        assert val is False

    def test_write_returns_ok(self, sim_backend):
        result = asyncio.get_event_loop().run_until_complete(
            sim_backend.write_io("start_light", True)
        )
        assert result["status"] == "ok"
        assert result["backend"] == "simulated"
        assert result["value"] is True

    def test_read_unknown_io(self, sim_backend):
        val = asyncio.get_event_loop().run_until_complete(sim_backend.read_io("nonexistent_io"))
        assert val is None

    def test_write_unknown_io(self, sim_backend):
        result = asyncio.get_event_loop().run_until_complete(
            sim_backend.write_io("nonexistent_io", True)
        )
        assert result["status"] == "error"


class TestSimulatedDependencies:
    """测试联动逻辑"""

    def test_grab_triggers_item_detected(self, sim_backend):
        """夹爪闭合 → sensor_item_detected = True"""
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("grab", True))
        val = asyncio.get_event_loop().run_until_complete(sim_backend.read_io("sensor_item_detected"))
        assert val is True

    def test_grab_release_clears_item_detected(self, sim_backend):
        """夹爪松开 → sensor_item_detected = False"""
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("grab", True))
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("grab", False))
        val = asyncio.get_event_loop().run_until_complete(sim_backend.read_io("sensor_item_detected"))
        assert val is False

    def test_arm_move_x_triggers_sensor(self, sim_backend):
        """arm_move_x=True → sensor_moving_x=True"""
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("arm_move_x", True))
        val = asyncio.get_event_loop().run_until_complete(sim_backend.read_io("sensor_moving_x"))
        assert val is True

    def test_arm_move_x_retract_clears_sensor(self, sim_backend):
        """arm_move_x=False → sensor_moving_x=False"""
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("arm_move_x", True))
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("arm_move_x", False))
        val = asyncio.get_event_loop().run_until_complete(sim_backend.read_io("sensor_moving_x"))
        assert val is False

    def test_arm_move_z_triggers_sensor(self, sim_backend):
        """arm_move_z=True → sensor_moving_z=True"""
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("arm_move_z", True))
        val = asyncio.get_event_loop().run_until_complete(sim_backend.read_io("sensor_moving_z"))
        assert val is True

    def test_arm_move_z_raise_clears_sensor(self, sim_backend):
        """arm_move_z=False → sensor_moving_z=False"""
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("arm_move_z", True))
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("arm_move_z", False))
        val = asyncio.get_event_loop().run_until_complete(sim_backend.read_io("sensor_moving_z"))
        assert val is False


class TestSimulatedEstop:
    """测试急停状态模拟"""

    def test_estop_default_false(self, sim_backend):
        val = asyncio.get_event_loop().run_until_complete(sim_backend.read_io("sensor_estop"))
        assert val is False

    def test_estop_blocks_output_write(self, sim_backend):
        """急停触发后，写入输出应被阻止"""
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("sensor_estop", True))
        result = asyncio.get_event_loop().run_until_complete(
            sim_backend.write_io("conveyor_entry", True)
        )
        assert result["status"] == "error"
        assert "急停" in result["error"]

    def test_estop_allows_sensor_write(self, sim_backend):
        """急停本身可以被设置/清除（传感器写入不受限）"""
        result = asyncio.get_event_loop().run_until_complete(
            sim_backend.write_io("sensor_estop", True)
        )
        assert result["status"] == "ok"
        val = asyncio.get_event_loop().run_until_complete(sim_backend.read_io("sensor_estop"))
        assert val is True

    def test_estop_release_allows_write(self, sim_backend):
        """急停解除后，写入应恢复正常"""
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("sensor_estop", True))
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("sensor_estop", False))
        result = asyncio.get_event_loop().run_until_complete(
            sim_backend.write_io("conveyor_entry", True)
        )
        assert result["status"] == "ok"


class TestSimulatedReadAllInputs:
    """测试 read_all_inputs 在模拟模式下"""

    def test_read_all_inputs_returns_all_sensors(self, sim_backend):
        inputs = asyncio.get_event_loop().run_until_complete(sim_backend.read_all_inputs())
        expected_sensors = [k for k in IO_MAP if k.startswith("sensor_")]
        for sensor in expected_sensors:
            assert sensor in inputs, f"{sensor} 应包含在 read_all_inputs 结果中"

    def test_read_all_inputs_reflects_state(self, sim_backend):
        asyncio.get_event_loop().run_until_complete(sim_backend.write_io("sensor_estop", True))
        inputs = asyncio.get_event_loop().run_until_complete(sim_backend.read_all_inputs())
        assert inputs["sensor_estop"] is True


class TestSimulatedBackendInfo:
    """测试 get_backend_info"""

    def test_backend_info_includes_simulated(self, sim_backend):
        info = sim_backend.get_backend_info()
        assert info["backend"] == "simulated"
        assert info["has_simulated"] is True


class TestEnvVarControl:
    """测试环境变量控制"""

    def test_env_var_sets_backend(self, monkeypatch):
        monkeypatch.setenv("ROBOT_BACKEND", "simulated")
        # 重新导入以触发 env var 读取
        import importlib
        importlib.reload(server)
        assert server.BACKEND == "simulated"
        # 恢复默认
        monkeypatch.setenv("ROBOT_BACKEND", "auto")
        importlib.reload(server)
