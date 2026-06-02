"""
把实例设成 Softbus STOP 状态，等 TIA Portal 下载
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

import clr
clr.AddReference(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\5.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll")
from Siemens.Simatic.Simulation.Runtime import (
    SimulationRuntimeManager, EOperatingState, ECommunicationInterface
)

instance = None
for info in SimulationRuntimeManager.RegisteredInstanceInfo:
    if info.Name == "factory io1":
        instance = SimulationRuntimeManager.CreateInterface(info.ID)
        break
if instance is None:
    print("❌ 未找到实例")
    exit(1)

print(f"当前状态: {instance.OperatingState}")

instance.CommunicationInterface = ECommunicationInterface.Softbus
instance.PowerOn()
time.sleep(3)
print(f"PowerOn: {instance.OperatingState}")

# 保持在 STOP 状态，让 TIA Portal 来下载
print(f"通信接口: {instance.CommunicationInterface}")
print("\n✅ 实例已就绪 (Softbus / STOP)")
print("   请在 TIA Portal 中下载到此实例")
