"""
黄金备份 — 简洁版
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

import clr
clr.AddReference(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\5.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll")
from Siemens.Simatic.Simulation.Runtime import (
    SimulationRuntimeManager, EOperatingState
)

BACKUP_DIR = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo"
ZIP_PATH = os.path.join(BACKUP_DIR, "factory_io1_golden.zip")

instance = None
for info in SimulationRuntimeManager.RegisteredInstanceInfo:
    if info.Name == "factory io1":
        instance = SimulationRuntimeManager.CreateInterface(info.ID)
        break
if instance is None:
    print("❌ 未找到")
    exit(1)

print(f"当前状态: {instance.OperatingState}")

# Stop (不需要 PowerOff)
print(">>> Stop ...")
instance.Stop()
time.sleep(2)
print(f"状态: {instance.OperatingState}")

# StoragePath
os.makedirs(BACKUP_DIR, exist_ok=True)
instance.StoragePath = BACKUP_DIR
time.sleep(1)
print(f"StoragePath = {BACKUP_DIR}")

# ArchiveStorage
print(f">>> ArchiveStorage -> {ZIP_PATH}")
instance.ArchiveStorage(ZIP_PATH)
time.sleep(2)

if os.path.exists(ZIP_PATH):
    size = os.path.getsize(ZIP_PATH)
    print(f"\n✅ 黄金备份已创建!")
    print(f"   路径: {ZIP_PATH}")
    print(f"   大小: {size/1024:.1f} KB")
else:
    print("\n❌ 失败")
    exit(1)

# 恢复
instance.PowerOn()
time.sleep(2)
instance.Run()
time.sleep(2)
print(f"最终: {instance.OperatingState}")
