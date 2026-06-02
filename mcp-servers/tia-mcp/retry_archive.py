"""
尝试正确创建归档：PowerOn → Stop → StoragePath → ArchiveStorage
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

print(f"1. 当前状态: {instance.OperatingState}")

# PowerOn → 应该有配置
if instance.OperatingState == EOperatingState.Off:
    print("2. PowerOn ...")
    instance.PowerOn()
    time.sleep(3)
    print(f"   状态: {instance.OperatingState}")

# 检查是不是有内容 (Run 试试)
if instance.OperatingState == EOperatingState.Stop:
    print("3. 试 Run ...")
    try:
        instance.Run()
        time.sleep(2)
        print(f"   状态: {instance.OperatingState} ✅ 有硬件配置!")
    except Exception as e:
        print(f"   ❌ 仍然空壳: {e}")
        print("\n需要重新 TIA Portal 下载")
        exit(1)

# 有配置了，现在 Stop → 存档
print("4. Stop ...")
instance.Stop()
time.sleep(2)
print(f"   状态: {instance.OperatingState}")

# 设置 StoragePath
os.makedirs(BACKUP_DIR, exist_ok=True)
instance.StoragePath = BACKUP_DIR
time.sleep(1)
print(f"5. StoragePath = {BACKUP_DIR}")

# ArchiveStorage
print(f"6. ArchiveStorage -> {ZIP_PATH} ...")
instance.ArchiveStorage(ZIP_PATH)
time.sleep(2)

if os.path.exists(ZIP_PATH):
    size = os.path.getsize(ZIP_PATH)
    print(f"\n✅ 黄金备份已创建!")
    print(f"   路径: {ZIP_PATH}")
    print(f"   大小: {size/1024:.1f} KB")
else:
    print(f"\n❌ 归档失败，文件未生成")
    exit(1)

# 恢复运行
print("\n7. 恢复 Run ...")
instance.CommunicationInterface = ECommunicationInterface.Softbus
instance.PowerOn()
time.sleep(2)
instance.Run()
time.sleep(2)
print(f"   最终状态: {instance.OperatingState}")
print("\n🎉 黄金备份创建完成！")
