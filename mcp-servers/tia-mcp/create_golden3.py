"""
创建黄金备份 v3 — 正确处理状态
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

import clr
clr.AddReference(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\5.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll")
from Siemens.Simatic.Simulation.Runtime import (
    SimulationRuntimeManager, EOperatingState, ECommunicationInterface
)

BACKUP_DIR = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo"
ZIP_PATH = os.path.join(BACKUP_DIR, "factory_io1_golden.zip")

instance = None
for info in SimulationRuntimeManager.RegisteredInstanceInfo:
    if info.Name == "factory io1":
        instance = SimulationRuntimeManager.CreateInterface(info.ID)
        break
if instance is None:
    print("❌ 未找到实例")
    exit(1)

print(f"当前状态: {instance.OperatingState}")

# 确保 Off
if instance.OperatingState == EOperatingState.Run:
    instance.Stop()
    time.sleep(2)
if instance.OperatingState == EOperatingState.Stop:
    instance.PowerOff()
    time.sleep(2)
print(f"当前状态: {instance.OperatingState}")

# 设置 StoragePath
os.makedirs(BACKUP_DIR, exist_ok=True)
try:
    instance.StoragePath = BACKUP_DIR
    print(f"✅ StoragePath = {BACKUP_DIR}")
except Exception as e:
    print(f"StoragePath 设置失败: {e}")
    methods = [m for m in dir(instance) if 'torage' in m.lower() or 'rchive' in m.lower()]
    print(f"相关方法: {methods}")
    exit(1)

time.sleep(1)

# ArchiveStorage
print(f">>> ArchiveStorage -> {ZIP_PATH} ...")
instance.ArchiveStorage(ZIP_PATH)
time.sleep(2)

if os.path.exists(ZIP_PATH):
    size = os.path.getsize(ZIP_PATH)
    print(f"\n✅ 黄金备份已创建!")
    print(f"   路径: {ZIP_PATH}")
    print(f"   大小: {size/1024:.1f} KB")
else:
    print(f"\n❌ 归档失败")
    exit(1)

# 恢复 Softbus Run
instance.CommunicationInterface = ECommunicationInterface.Softbus
instance.PowerOn()
time.sleep(3)
instance.Run()
time.sleep(3)
print(f"最终状态: {instance.OperatingState}")
print("\n✅ 完成！黄金备份已就绪")
