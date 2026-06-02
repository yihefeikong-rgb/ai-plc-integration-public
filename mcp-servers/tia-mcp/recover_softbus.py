"""
恢复实例到 Softbus 模式
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
print(f"当前通信接口: {instance.CommunicationInterface}")

instance.CommunicationInterface = ECommunicationInterface.Softbus
print("已切回 Softbus")

instance.PowerOn()
time.sleep(3)
print(f"PowerOn 后状态: {instance.OperatingState}")

instance.Run()
time.sleep(3)
print(f"Run 后状态: {instance.OperatingState}")

if instance.OperatingState == EOperatingState.Run:
    print("\n✅ 已恢复 Softbus RUN 模式")
else:
    print(f"\n⚠️ 状态: {instance.OperatingState}")
