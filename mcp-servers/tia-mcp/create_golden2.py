"""
创建黄金备份 v2 — 用 StoragePath 属性
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

# Stop + PowerOff
instance.Stop()
time.sleep(2)
instance.PowerOff()
time.sleep(2)
print(f"PowerOff 后状态: {instance.OperatingState}")

# 尝试 StoragePath 属性
os.makedirs(BACKUP_DIR, exist_ok=True)
try:
    instance.StoragePath = BACKUP_DIR
    print(f"StoragePath 已设置为: {BACKUP_DIR}")
except:
    print("StoragePath 属性设置失败，尝试备用方法...")
    # 看看有哪些可用方法
    methods = [m for m in dir(instance) if 'torage' in m.lower() or 'rchive' in m.lower()]
    print(f"可用方法: {methods}")
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

# 恢复运行
instance.CommunicationInterface = ECommunicationInterface.Softbus
instance.PowerOn()
time.sleep(2)
instance.Run()
time.sleep(2)
print(f"最终状态: {instance.OperatingState}")
print("\n✅ 完成！")
