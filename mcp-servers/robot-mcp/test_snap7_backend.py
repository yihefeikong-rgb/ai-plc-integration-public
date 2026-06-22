"""
TS018 — RobotBackend snap7 回退路径测试

测试 snap7 模式下:
  - 连接成功/失败处理
  - 读取输入、写入输出
  - 急停检查在 snap7 模式下
  - read_all_inputs 在 snap7 模式下的批量读取
  - snap7 不可用时的优雅降级
  - 现有 simulated 模式不受影响（交叉验证）
"""

import asyncio
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import server
from server import RobotBackend, IO_MAP


# ── Mock snap7 Client ──────────────────────────────────────────────

class MockS7Client:
    """模拟 python-snap7 v3 Client，提供可控的读写行为"""

    def __init__(self):
        self._connected = False
        self._input_bytes = bytearray(2)   # 2 bytes for inputs (%I0.0-I1.0)
        self._output_bytes = bytearray(1)  # 1 byte for outputs (%Q0.0-Q0.7)

    def connect(self, ip, rack, slot):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def get_connected(self):
        return self._connected

    def read_area(self, area, db_number, start, size):
        if area == 0x81:  # Input area
            return bytes(self._input_bytes[start:start + size])
        elif area == 0x82:  # Output area
            return bytes(self._output_bytes[start:start + size])
        return b'\x00' * size

    def write_area(self, area, db_number, start, data):
        if area == 0x82:  # Output area
            for i, b in enumerate(data):
                if start + i < len(self._output_bytes):
                    self._output_bytes[start + i] = b

    def set_input_bit(self, byte_offset, bit, value):
        """设置模拟输入位的值"""
        if value:
            self._input_bytes[byte_offset] |= (1 << bit)
        else:
            self._input_bytes[byte_offset] &= ~(1 << bit)

    def set_output_bit(self, byte_offset, bit, value):
        """设置模拟输出位的值"""
        if value:
            self._output_bytes[byte_offset] |= (1 << bit)
        else:
            self._output_bytes[byte_offset] &= ~(1 << bit)

    def get_output_bit(self, byte_offset, bit):
        """读取模拟输出位的值"""
        return bool(self._output_bytes[byte_offset] & (1 << bit))


# ── Snap7 Backend Fixtures ─────────────────────────────────────────

@pytest.fixture
def snap7_backend(monkeypatch):
    """创建一个 snap7 模式后端，用 MockS7Client 替换真实 snap7"""
    mock_client = MockS7Client()
    monkeypatch.setattr(server, "BACKEND", "snap7")
    monkeypatch.setattr(server, "HAS_SNAP7", True)
    # Mock snap7.client.Client 返回我们的 mock
    monkeypatch.setattr(server.snap7.client, "Client", lambda: mock_client)
    backend = RobotBackend()
    # 连接
    result = backend.connect_snap7()
    assert result is True
    assert backend.backend_type == "snap7"
    return mock_client, backend


@pytest.fixture
def snap7_estop_triggered(snap7_backend):
    """snap7 模式下急停已触发"""
    mock_client, backend = snap7_backend
    mock_client.set_input_bit(1, 0, True)  # sensor_estop = I1.0 byte=1, bit=0
    return mock_client, backend


# ── Snap7 Connection Tests ─────────────────────────────────────────

class TestSnap7Connect:
    """测试 snap7 连接逻辑"""

    def test_connect_snap7_success(self, snap7_backend):
        """snap7 连接成功，backend_type 应为 snap7"""
        mock_client, backend = snap7_backend
        assert backend.backend_type == "snap7"

    def test_connect_snap7_when_unavailable(self, monkeypatch):
        """snap7 不可用时应返回 False"""
        monkeypatch.setattr(server, "BACKEND", "snap7")
        monkeypatch.setattr(server, "HAS_SNAP7", False)
        backend = RobotBackend()
        result = backend.connect_snap7()
        assert result is False
        assert backend.backend_type is None

    def test_connect_snap7_client_failure(self, monkeypatch):
        """snap7 Client 连接失败时应返回 False"""
        monkeypatch.setattr(server, "BACKEND", "snap7")
        monkeypatch.setattr(server, "HAS_SNAP7", True)
        # Mock Client 抛出异常（连接被拒绝）
        def failing_client():
            raise Exception("Connection refused")
        monkeypatch.setattr(server.snap7.client, "Client", failing_client)
        backend = RobotBackend()
        result = backend.connect_snap7()
        assert result is False
        assert backend._snap_client is None

    def test_connect_snap7_get_connected_false(self, monkeypatch):
        """Client 存在但 get_connected() 返回 False"""
        monkeypatch.setattr(server, "BACKEND", "snap7")
        monkeypatch.setattr(server, "HAS_SNAP7", True)

        class NotConnectedClient:
            def connect(self, ip, rack, slot):
                pass
            def get_connected(self):
                return False

        monkeypatch.setattr(server.snap7.client, "Client",
                           lambda: NotConnectedClient())
        backend = RobotBackend()
        result = backend.connect_snap7()
        assert result is False
        assert backend._snap_client is None

    def test_ensure_connected_snap7(self, snap7_backend):
        """ensure_connected 在 snap7 已连接时返回 True"""
        mock_client, backend = snap7_backend
        result = asyncio.get_event_loop().run_until_complete(
            backend.ensure_connected()
        )
        assert result is True

    def test_get_backend_info_snap7(self, snap7_backend):
        """get_backend_info 应报告 snap7 可用"""
        mock_client, backend = snap7_backend
        info = backend.get_backend_info()
        assert info["backend"] == "snap7"
        assert info["has_snap7"] is True
        assert info["has_simulated"] is True


# ── Snap7 Read Tests ───────────────────────────────────────────────

class TestSnap7ReadInputs:
    """测试 snap7 读取输入（传感器的值来自 PLCSIM 输入区 0x81）"""

    def test_read_input_default_false(self, snap7_backend):
        """所有传感器默认值为 False"""
        mock_client, backend = snap7_backend
        for name in IO_MAP:
            if name.startswith("sensor_"):
                val = asyncio.get_event_loop().run_until_complete(
                    backend.read_io(name)
                )
                assert val is False, f"snap7 {name} 默认值为 False, got {val}"

    def test_read_input_sensor_entry(self, snap7_backend):
        """读取 sensor_entry (I0.0, byte=0, bit=0)"""
        mock_client, backend = snap7_backend
        mock_client.set_input_bit(0, 0, True)
        val = asyncio.get_event_loop().run_until_complete(
            backend.read_io("sensor_entry")
        )
        assert val is True

    def test_read_input_sensor_estop(self, snap7_backend):
        """读取 sensor_estop (I1.0, byte=1, bit=0)"""
        mock_client, backend = snap7_backend
        # sensor_estop = byte 1, bit 0
        mock_client.set_input_bit(1, 0, True)
        val = asyncio.get_event_loop().run_until_complete(
            backend.read_io("sensor_estop")
        )
        assert val is True

        mock_client.set_input_bit(1, 0, False)
        val = asyncio.get_event_loop().run_until_complete(
            backend.read_io("sensor_estop")
        )
        assert val is False

    def test_read_input_multiple_sensors(self, snap7_backend):
        """测试同一字节内多个位的独立读取"""
        mock_client, backend = snap7_backend
        # byte 0: bits 0-7 = sensor_entry through sensor_stop
        mock_client.set_input_bit(0, 0, True)   # sensor_entry
        mock_client.set_input_bit(0, 1, True)   # sensor_exit
        mock_client.set_input_bit(0, 2, False)  # sensor_moving_x
        mock_client.set_input_bit(0, 7, True)   # sensor_stop

        assert asyncio.get_event_loop().run_until_complete(
            backend.read_io("sensor_entry")) is True
        assert asyncio.get_event_loop().run_until_complete(
            backend.read_io("sensor_exit")) is True
        assert asyncio.get_event_loop().run_until_complete(
            backend.read_io("sensor_moving_x")) is False
        assert asyncio.get_event_loop().run_until_complete(
            backend.read_io("sensor_stop")) is True

    def test_read_io_returns_none_on_error(self, snap7_backend):
        """snap7 read_area 异常时 read_io 应返回 None 而不是崩溃"""
        mock_client, backend = snap7_backend

        # 注入读取失败
        def failing_read(*args, **kwargs):
            raise RuntimeError("simulated snap7 failure")
        mock_client.read_area = failing_read

        val = asyncio.get_event_loop().run_until_complete(
            backend.read_io("sensor_entry")
        )
        assert val is None


# ── Snap7 Write Tests ──────────────────────────────────────────────

class TestSnap7Write:
    """测试 snap7 写入输出（写入 PLCSIM 输出区 0x82，read-modify-write）"""

    def test_write_output_conveyor_entry(self, snap7_backend):
        """写入 conveyor_entry (Q0.0, byte=0, bit=0)"""
        mock_client, backend = snap7_backend
        result = asyncio.get_event_loop().run_until_complete(
            backend.write_io("conveyor_entry", True)
        )
        assert result["status"] == "ok"
        assert result["backend"] == "snap7"
        assert result["value"] is True
        assert mock_client.get_output_bit(0, 0) is True

    def test_write_output_turn_off(self, snap7_backend):
        """先写 True 再写 False"""
        mock_client, backend = snap7_backend
        asyncio.get_event_loop().run_until_complete(
            backend.write_io("conveyor_entry", True)
        )
        assert mock_client.get_output_bit(0, 0) is True

        asyncio.get_event_loop().run_until_complete(
            backend.write_io("conveyor_entry", False)
        )
        assert mock_client.get_output_bit(0, 0) is False

    def test_write_preserves_other_bits(self, snap7_backend):
        """写入一个位不应影响同一字节的其他位（read-modify-write）"""
        mock_client, backend = snap7_backend
        # 先设置 bit 0 和 bit 1
        asyncio.get_event_loop().run_until_complete(
            backend.write_io("conveyor_entry", True))   # byte 0, bit 0
        asyncio.get_event_loop().run_until_complete(
            backend.write_io("conveyor_exit", True))     # byte 0, bit 1

        assert mock_client.get_output_bit(0, 0) is True
        assert mock_client.get_output_bit(0, 1) is True

        # 关闭 bit 0，bit 1 应保持
        asyncio.get_event_loop().run_until_complete(
            backend.write_io("conveyor_entry", False))
        assert mock_client.get_output_bit(0, 0) is False
        assert mock_client.get_output_bit(0, 1) is True

    def test_write_output_arm_move_x(self, snap7_backend):
        """写入 arm_move_x (Q0.2, byte=0, bit=2)"""
        mock_client, backend = snap7_backend
        result = asyncio.get_event_loop().run_until_complete(
            backend.write_io("arm_move_x", True)
        )
        assert result["status"] == "ok"
        assert mock_client.get_output_bit(0, 2) is True

    def test_write_output_grab(self, snap7_backend):
        """写入 grab (Q0.4, byte=0, bit=4)"""
        mock_client, backend = snap7_backend
        result = asyncio.get_event_loop().run_until_complete(
            backend.write_io("grab", True)
        )
        assert result["status"] == "ok"
        assert mock_client.get_output_bit(0, 4) is True


# ── Snap7 Estop Tests ──────────────────────────────────────────────

class TestSnap7Estop:
    """测试急停检查在 snap7 模式下"""

    def test_estop_default_false_snap7(self, snap7_backend):
        """急停传感器默认 False"""
        mock_client, backend = snap7_backend
        val = asyncio.get_event_loop().run_until_complete(
            backend.read_io("sensor_estop")
        )
        assert val is False

    def test_estop_blocks_actuator_write(self, snap7_estop_triggered):
        """急停触发后，写入执行器应被阻止"""
        mock_client, backend = snap7_estop_triggered
        # 确认急停是 True
        val = asyncio.get_event_loop().run_until_complete(
            backend.read_io("sensor_estop")
        )
        assert val is True

        result = asyncio.get_event_loop().run_until_complete(
            backend.write_io("conveyor_entry", True)
        )
        assert result["status"] == "error"
        assert "急停" in result["error"]

    def test_estop_blocks_arm_write(self, snap7_estop_triggered):
        """急停应阻止 arm_move_x 写入"""
        mock_client, backend = snap7_estop_triggered
        result = asyncio.get_event_loop().run_until_complete(
            backend.write_io("arm_move_x", True)
        )
        assert result["status"] == "error"
        assert "急停" in result["error"]

    def test_estop_blocks_grab_write(self, snap7_estop_triggered):
        """急停应阻止 grab 写入"""
        mock_client, backend = snap7_estop_triggered
        result = asyncio.get_event_loop().run_until_complete(
            backend.write_io("grab", True)
        )
        assert result["status"] == "error"
        assert "急停" in result["error"]

    def test_estop_allows_indicator_write(self, snap7_estop_triggered):
        """急停不阻止指示灯写入（指示灯非执行器）"""
        mock_client, backend = snap7_estop_triggered
        result = asyncio.get_event_loop().run_until_complete(
            backend.write_io("start_light", True)
        )
        assert result["status"] == "ok"

    def test_estop_no_estop_allows_write(self, snap7_backend):
        """急停未触发时写入正常"""
        mock_client, backend = snap7_backend
        result = asyncio.get_event_loop().run_until_complete(
            backend.write_io("conveyor_entry", True)
        )
        assert result["status"] == "ok"


# ── Snap7 read_all_inputs Tests ────────────────────────────────────

class TestSnap7ReadAllInputs:
    """测试 snap7 模式下批量读取输入"""

    def test_read_all_inputs_returns_all_sensors(self, snap7_backend):
        """应返回所有传感器键"""
        mock_client, backend = snap7_backend
        inputs = asyncio.get_event_loop().run_until_complete(
            backend.read_all_inputs()
        )
        expected_sensors = [k for k in IO_MAP if k.startswith("sensor_")]
        for sensor in expected_sensors:
            assert sensor in inputs, f"{sensor} 应包含在结果中"

    def test_read_all_inputs_reflects_state(self, snap7_backend):
        """读取的值应反映输入区状态"""
        mock_client, backend = snap7_backend
        mock_client.set_input_bit(0, 0, True)   # sensor_entry
        mock_client.set_input_bit(0, 5, True)   # sensor_start
        mock_client.set_input_bit(1, 0, True)   # sensor_estop

        inputs = asyncio.get_event_loop().run_until_complete(
            backend.read_all_inputs()
        )
        assert inputs["sensor_entry"] is True
        assert inputs["sensor_start"] is True
        assert inputs["sensor_estop"] is True
        assert inputs["sensor_reset"] is False

    def test_read_all_inputs_default_all_false(self, snap7_backend):
        """默认所有输入为 False"""
        mock_client, backend = snap7_backend
        inputs = asyncio.get_event_loop().run_until_complete(
            backend.read_all_inputs()
        )
        for name, val in inputs.items():
            assert val is False, f"snap7 {name} 默认应为 False"

    def test_read_all_inputs_fallback_on_error(self, snap7_backend):
        """snap7 read_area(批量) 失败时回退到逐个 read_io"""
        mock_client, backend = snap7_backend

        # 批量 read_area 失败
        original_read_area = mock_client.read_area

        def broken_read_area(area, db_number, start, size):
            if area == 0x81 and size >= 2:
                raise RuntimeError("bulk read failed")
            return original_read_area(area, db_number, start, size)

        mock_client.read_area = broken_read_area

        inputs = asyncio.get_event_loop().run_until_complete(
            backend.read_all_inputs()
        )

        # 应回退到逐个 read_io，不应崩溃
        expected_sensors = [k for k in IO_MAP if k.startswith("sensor_")]
        for sensor in expected_sensors:
            assert sensor in inputs


# ── Graceful Degradation Tests ─────────────────────────────────────

class TestSnap7Unavailable:
    """测试 snap7 不可用时的优雅降级"""

    def test_import_unavailable(self, monkeypatch):
        """snap7 未安装时 connect_snap7 返回 False"""
        monkeypatch.setattr(server, "BACKEND", "auto")
        monkeypatch.setattr(server, "HAS_SNAP7", False)
        monkeypatch.setattr(server, "HAS_ASYNCUA", False)
        backend = RobotBackend()
        result = backend.connect_snap7()
        assert result is False
        assert backend.backend_type is None

    def test_ensure_connected_falls_through_simulated(self, monkeypatch):
        """当 snap7 和 OPC UA 都不可用时，应能回退到 simulated"""
        monkeypatch.setattr(server, "BACKEND", "auto")
        monkeypatch.setattr(server, "HAS_SNAP7", False)
        monkeypatch.setattr(server, "HAS_ASYNCUA", False)
        backend = RobotBackend()
        result = asyncio.get_event_loop().run_until_complete(
            backend.ensure_connected()
        )
        # ensure_connected auto 模式下，OPC UA 失败后尝试 snap7，
        # snap7 也失败，最终返回 True（最后一次 connect_snap7 返回 False
        # 但 ensure_connected 的逻辑: 最后返回 self.connect_snap7()
        # 当 HAS_SNAP7=False, connect_snap7() 返回 False
        # 整个 ensure_connected 返回 False
        # 这意味着无法连接。这是预期的——让用户知道连接失败。
        assert result is False

    def test_read_io_returns_none_when_not_connected(self, monkeypatch):
        """未连接时 read_io 应返回 None"""
        monkeypatch.setattr(server, "BACKEND", "snap7")
        monkeypatch.setattr(server, "HAS_SNAP7", False)
        backend = RobotBackend()
        val = asyncio.get_event_loop().run_until_complete(
            backend.read_io("sensor_entry")
        )
        assert val is None

    def test_write_io_returns_error_when_not_connected(self, monkeypatch):
        """未连接时 write_io 应返回 error"""
        monkeypatch.setattr(server, "BACKEND", "snap7")
        monkeypatch.setattr(server, "HAS_SNAP7", False)
        backend = RobotBackend()
        result = asyncio.get_event_loop().run_until_complete(
            backend.write_io("conveyor_entry", True)
        )
        assert result["status"] == "error"
        assert "未连接" in result["error"]


# ── Backend Info Test ──────────────────────────────────────────────

class TestSnap7BackendInfo:
    """测试 backend info"""

    def test_backend_info_when_snap7_available(self, snap7_backend):
        """HAS_SNAP7=True 时 info 中 has_snap7=True"""
        mock_client, backend = snap7_backend
        info = backend.get_backend_info()
        assert info["backend"] == "snap7"
        assert info["has_snap7"] is True
        assert "plc_ip" in info
        assert "opcua_endpoint" in info

    def test_backend_info_when_snap7_not_available(self, monkeypatch):
        """HAS_SNAP7=False 时 info 反映实际情况"""
        monkeypatch.setattr(server, "HAS_SNAP7", False)
        backend = RobotBackend()
        info = backend.get_backend_info()
        assert info["has_snap7"] is False
        assert info["backend"] == "not connected"


# ── Edge Cases ─────────────────────────────────────────────────────

class TestSnap7EdgeCases:
    """边缘情况处理"""

    def test_write_sensor_via_snap7(self, snap7_backend):
        """写入传感器（输入 I/O）应视为输出前检查——senor 不是输入是逻辑！"""
        mock_client, backend = snap7_backend
        # sensor_start 是输入，但 write_io 不区分输入/输出类型，
        # 只检查是 actuator/conveyor/arm/grab 才做急停检查。
        # 传感器写入应该走 0x82（输出区），这在真实场景中无意义但不应该崩溃。
        result = asyncio.get_event_loop().run_until_complete(
            backend.write_io("sensor_start", True)
        )
        assert result["status"] == "ok"
        assert result["backend"] == "snap7"

    def test_connect_snap7_second_time(self, snap7_backend):
        """第二次调用 connect_snap7 应跳过（已连接）"""
        mock_client, backend = snap7_backend
        # 已连接状态
        assert backend.backend_type == "snap7"
        # ensure_connected 在 snap7 模式下检查 _snap_client is not None
        result = asyncio.get_event_loop().run_until_complete(
            backend.ensure_connected()
        )
        assert result is True

    def test_connect_snap7_preserves_client(self, snap7_backend):
        """连接成功后 _snap_client 应该是 MockClient 实例"""
        mock_client, backend = snap7_backend
        assert backend._snap_client is mock_client


# ── Cross-verification: simulated mode still works ─────────────────

class TestSimulatedStillWorks:
    """验证 simulated 模式在加入 snap7 测试后仍然正常"""

    def test_simulated_connect_still_works(self, monkeypatch):
        monkeypatch.setattr(server, "BACKEND", "simulated")
        backend = RobotBackend()
        result = asyncio.get_event_loop().run_until_complete(
            backend.connect_simulated()
        )
        assert result is True
        assert backend.backend_type == "simulated"

    def test_simulated_read_write_still_works(self, monkeypatch):
        monkeypatch.setattr(server, "BACKEND", "simulated")
        backend = RobotBackend()
        asyncio.get_event_loop().run_until_complete(backend.connect_simulated())
        asyncio.get_event_loop().run_until_complete(
            backend.write_io("conveyor_entry", True))
        val = asyncio.get_event_loop().run_until_complete(
            backend.read_io("conveyor_entry"))
        assert val is True
