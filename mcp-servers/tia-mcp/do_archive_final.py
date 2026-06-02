"""
黄金备份 — StoragePath 已持久化，归档
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

import clr
clr.AddReference(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\5.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll")
from Siemens.Simatic.Simulation.Runtime import (
    SimulationRuntimeManager, EOperatingState
)

ZIP_PATH = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\factory_io1_golden.zip"

instance = None
for info in SimulationRuntimeManager.RegisteredInstanceInfo:
    if info.Name == "factory io1":
        instance = SimulationRuntimeManager.CreateInterface(info.ID)
        break
if instance is None:
    print("❌ 未找到")
    exit(1)

print(f"1. 当前: {instance.OperatingState}")
print(f"   StoragePath: {instance.StoragePath}")

# Stop → PowerOff
instance.Stop()
time.sleep(2)
instance.PowerOff()
time.sleep(2)
print(f"2. PowerOff: {instance.OperatingState}")

# ArchiveStorage
print(f"3. ArchiveStorage -> {ZIP_PATH}")
instance.ArchiveStorage(ZIP_PATH)
time.sleep(2)

if os.path.exists(ZIP_PATH):
    size = os.path.getsize(ZIP_PATH)
    print(f"\n✅ 黄金备份已创建! {size/1024:.1f} KB")
    print(f"   路径: {ZIP_PATH}")
else:
    print("\n❌ 失败")
    exit(1)

# 恢复 Softbus RUN
instance.CommunicationInterface = ECommunicationInterface.Softbus
instance.PowerOn()
time.sleep(2)
instance.Run()
time.sleep(2)
print(f"4. 恢复: {instance.OperatingState}")
print("\n🎉 完成！")
