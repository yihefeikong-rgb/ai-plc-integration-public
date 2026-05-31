"""Modbus TCP 仿真 PLC — 用于 MCP Server 测试"""
from pymodbus.server import StartTcpServer
from pymodbus.simulator import SimDevice, SimData
from pymodbus.simulator.simdata import DataType

device = SimDevice(
    id=1,
    simdata=(
        [SimData(0, count=10, values=[False] * 10, datatype=DataType.BITS)],                                              # 0: 线圈 (coils)
        [SimData(0, count=10, values=[True, False, False, True, False, False, False, False, False, False], datatype=DataType.BITS)],  # 1: 离散输入 (discrete inputs)
        [SimData(0, count=10, values=[250, 30, 150, 0, 0, 0, 0, 0, 0, 0], datatype=DataType.UINT16)],                    # 2: 保持寄存器 (holding registers)
        [SimData(0, count=1, values=0, datatype=DataType.UINT16)],                                                # 3: 输入寄存器 (input registers)
    ),
)

print("Modbus PLC 仿真 localhost:502 已启动")
print("线圈 0-9 | 寄存器 0-9 (250,30,150...) | 离散输入 0-9")
StartTcpServer(context=device, address=("localhost", 502))
