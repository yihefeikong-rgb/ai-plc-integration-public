"""
黄金备份 v3 — 在 Stop 状态下设置 StoragePath 再归档
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

print(f"1. 当前状态: {instance.OperatingState}")

# 必须先 PowerOn 才能访问虚拟存储卡
if instance.OperatingState == EOperatingState.Off:
    instance.PowerOn()
    time.sleep(3)
    print(f"2. PowerOn: {instance.OperatingState}")

# Stop (不能在 Run 状态归档)
if instance.OperatingState == EOperatingState.Run:
    instance.Stop()
    time.sleep(2)
    print(f"3. Stop: {instance.OperatingState}")

# 现在在 Stop 状态设 StoragePath
os.makedirs(BACKUP_DIR, exist_ok=True)
instance.StoragePath = BACKUP_DIR
print(f"4. StoragePath = {BACKUP_DIR}")

# 尝试 ArchiveStorage (在 Stop 状态)
try:
    print(f"5. ArchiveStorage...")
    instance.ArchiveStorage(ZIP_PATH)
    time.sleep(2)
except Exception as e:
    print(f"   Stop 状态失败: {e}")
    print(f"   试试 PowerOff 后归档...")
    instance.PowerOff()
    time.sleep(2)
    instance.ArchiveStorage(ZIP_PATH)
    time.sleep(2)

if os.path.exists(ZIP_PATH):
    size = os.path.getsize(ZIP_PATH)
    print(f"\n✅ 黄金备份已创建! {size/1024:.1f} KB")
else:
    # 看看是不是路径问题
    print(f"\n❌ 失败，检查目录:")
    print(f"   {BACKUP_DIR}")
    print(f"   内容: {os.listdir(BACKUP_DIR)}")
    exit(1)

# 恢复
instance.PowerOn()
time.sleep(2)
instance.Run()
time.sleep(2)
print(f"6. 最终: {instance.OperatingState}")
