"""
检查实例是否有硬件配置：PowerOn + Run 试一下
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
print(f"通信接口: {instance.CommunicationInterface}")

# PowerOn
print("\n>>> PowerOn ...")
instance.PowerOn()
time.sleep(3)
print(f"状态: {instance.OperatingState}")

# Try Run
if instance.OperatingState == EOperatingState.Stop:
    print("\n>>> Run ...")
    instance.Run()
    time.sleep(3)
    print(f"状态: {instance.OperatingState}")

print(f"\n最终状态: {instance.OperatingState}")
if instance.OperatingState == EOperatingState.Run:
    print("✅ 有硬件配置！TIA Portal 下载成功")
else:
    print("⚠️ 没有硬件配置（空壳 CPU），需要重新下载")
