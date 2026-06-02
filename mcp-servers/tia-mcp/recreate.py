"""
在 Softbus 模式下重建 factory io1 并尝试启动
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

import clr
clr.AddReference(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\5.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll")
from Siemens.Simatic.Simulation.Runtime import (
    SimulationRuntimeManager, EOperatingState, ECommunicationInterface
)

# 1. 注册实例 (Softbus)
cpu_type = None
for name in dir(SimulationRuntimeManager):
    if name.startswith("CPU"):
        pass
from Siemens.Simatic.Simulation.Runtime import ECPUType

cpu = ECPUType.CPU1511
instance = SimulationRuntimeManager.RegisterInstance(cpu, "factory io1")
print(f"已注册: factory io1")

# 2. 设置 Softbus
instance.CommunicationInterface = ECommunicationInterface.Softbus
print(f"通信接口: Softbus")

# 3. PowerOn
print("PowerOn ...")
instance.PowerOn()
time.sleep(3)
print(f"状态: {instance.OperatingState}")

# 4. Run
print("Run ...")
instance.Run()
time.sleep(3)
print(f"状态: {instance.OperatingState}")

if instance.OperatingState == EOperatingState.Run:
    print("\n✅ factory io1 已 RUN (Softbus)")
    print("\n注意：之前 TIA Portal 下载的硬件配置已丢失")
    print("需要重新下载，或者下一步用 ArchiveStorage 保存后恢复")
else:
    print(f"\n⚠️ 状态: {instance.OperatingState}")
