"""
设置 StoragePath，然后起 Softbus STOP，等 TIA Portal 下载
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

import clr
clr.AddReference(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\5.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll")
from Siemens.Simatic.Simulation.Runtime import (
    SimulationRuntimeManager, EOperatingState, ECommunicationInterface
)

STORAGE_DIR = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\plcsim_storage"

# 先删旧实例重建
for info in list(SimulationRuntimeManager.RegisteredInstanceInfo):
    if info.Name == "factory io1":
        inst = SimulationRuntimeManager.CreateInterface(info.ID)
        try:
            inst.Stop()
        except: pass
        try:
            inst.PowerOff()
        except: pass
        inst.UnregisterInstance()
        print("已删除旧实例")
        time.sleep(1)

# 创建新实例
from Siemens.Simatic.Simulation.Runtime import ECPUType
instance = SimulationRuntimeManager.RegisterInstance(ECPUType.CPU1511, "factory io1")
print("已注册 factory io1")

# 设置 Softbus
instance.CommunicationInterface = ECommunicationInterface.Softbus

# 关键：先设置 StoragePath
os.makedirs(STORAGE_DIR, exist_ok=True)
instance.StoragePath = STORAGE_DIR
print(f"StoragePath = {STORAGE_DIR}")

# PowerOn (Softbus, STOP 状态)
instance.PowerOn()
time.sleep(3)
print(f"状态: {instance.OperatingState}")

print("\n✅ 已就绪！请 TIA Portal 下载到 factory io1")
print(f"   下载后数据会持久化到: {STORAGE_DIR}")
