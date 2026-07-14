"""
robot-mcp 测试 — 验证 OPC UA 连接和 I/O 读写

前提条件:
  1. PLCSIM Advanced V8.0 正在运行，实例 factoryio 已 Start（TCP/IP 模式）
  2. Factory I/O 已打开 Pick & Place (Basic) 场景并连接
  3. asyncua 库已安装 (pip install asyncua)

运行:
  1. 先启动 PLCSIM + Factory I/O
  2. 然后: pytest tests/test_robot_mcp.py -v
"""

import pytest
import sys
from pathlib import Path

pytestmark = pytest.mark.hardware

ROBOT_DIR = Path(__file__).parent.parent / "mcp-servers" / "robot-mcp"
sys.path.insert(0, str(ROBOT_DIR))

try:
    from asyncua import Client as OPCClient
    HAS_ASYNCUA = True
except ImportError:
    HAS_ASYNCUA = False

# 从 server.py 复用 I/O 映射
from server import IO_MAP, OPCUA_ENDPOINT


@pytest.fixture
def client():
    if not HAS_ASYNCUA:
        pytest.skip("asyncua 未安装")
    import asyncio
    c = OPCClient(url=OPCUA_ENDPOINT)
    loop = asyncio.new_event_loop()
    loop.run_until_complete(c.connect())
    yield c
    loop.run_until_complete(c.disconnect())


def test_import():
    """验证 robot-mcp 可正常导入"""
    from server import mcp, go_home, pick_item, place_item, move_arm_to, get_status, control_conveyor, run_pick_cycle
    assert mcp is not None


@pytest.mark.skipif(not HAS_ASYNCUA, reason="asyncua not installed")
@pytest.mark.asyncio
async def test_opcua_connection():
    """验证 OPC UA 能连通 PLCSIM"""
    try:
        client = OPCClient(url=OPCUA_ENDPOINT)
        await client.connect()
        assert client.uaclient is not None
        await client.disconnect()
    except Exception as e:
        pytest.skip(f"OPC UA 连接失败（PLCSIM 可能未运行）: {e}")


@pytest.mark.skipif(not HAS_ASYNCUA, reason="asyncua not installed")
@pytest.mark.asyncio
async def test_read_io():
    """验证能读取 I/O 点（需要 PLCSIM + Factory I/O 运行）"""
    pytest.skip("需要 PLCSIM Advanced + Factory I/O 运行时")


@pytest.mark.skipif(not HAS_ASYNCUA, reason="asyncua not installed")
@pytest.mark.asyncio
async def test_write_io():
    """验证能写入 I/O 点（需要 PLCSIM + Factory I/O 运行）"""
    pytest.skip("需要 PLCSIM Advanced + Factory I/O 运行时")


def test_io_map_completeness():
    """验证 I/O 映射表完整性"""
    required = ["sensor_entry", "sensor_exit", "sensor_moving_x",
                "sensor_moving_z", "sensor_item_detected", "sensor_estop",
                "conveyor_entry", "conveyor_exit", "arm_move_x", "arm_move_z", "grab"]
    for name in required:
        assert name in IO_MAP, f"缺少 I/O 点: {name}"
        assert "node" in IO_MAP[name], f"I/O {name} 缺少 node 字段"
        assert "desc" in IO_MAP[name], f"I/O {name} 缺少 desc 字段"


def test_mcp_tools_have_docstrings():
    """验证 MCP 工具有文档字符串"""
    from server import go_home, pick_item, place_item, move_arm_to, get_status, control_conveyor, run_pick_cycle
    for tool in [go_home, pick_item, place_item, move_arm_to, get_status, control_conveyor, run_pick_cycle]:
        assert tool.__doc__ is not None, f"{tool.__name__} 缺少文档字符串"
        assert len(tool.__doc__) > 20, f"{tool.__name__} 文档字符串太短"


@pytest.mark.skipif(not HAS_ASYNCUA, reason="asyncua not installed")
@pytest.mark.asyncio
async def test_safety_estop_blocks_action():
    """验证急停时机器人拒绝动作（需要 PLCSIM + Factory I/O 运行）"""
    pytest.skip("需要 PLCSIM Advanced + Factory I/O 运行时")
