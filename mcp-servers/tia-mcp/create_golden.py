"""
创建黄金备份：将当前已配置的 factory io1 归档为 ZIP
流程: Run → Stop → PowerOff → SetStoragePath → ArchiveStorage → 完成
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

# 1. 找到实例
instance = None
for info in SimulationRuntimeManager.RegisteredInstanceInfo:
    if info.Name == "factory io1":
        instance = SimulationRuntimeManager.CreateInterface(info.ID)
        break
if instance is None:
    print("❌ 未找到实例 factory io1")
    exit(1)

print(f"当前状态: {instance.OperatingState}")

# 2. Stop
print(">>> Stop ...")
instance.Stop()
time.sleep(2)
print(f"状态: {instance.OperatingState}")

# 3. PowerOff
print(">>> PowerOff ...")
instance.PowerOff()
time.sleep(2)
print(f"状态: {instance.OperatingState}")

# 4. 设置存储路径
print(f">>> SetStoragePath ...")
os.makedirs(BACKUP_DIR, exist_ok=True)
instance.SetStoragePath(BACKUP_DIR)
time.sleep(1)
print(f"StoragePath: {BACKUP_DIR}")

# 5. ArchiveStorage
print(f">>> ArchiveStorage -> {ZIP_PATH} ...")
instance.ArchiveStorage(ZIP_PATH)
time.sleep(2)

# 验证
if os.path.exists(ZIP_PATH):
    size = os.path.getsize(ZIP_PATH)
    print(f"\n✅ 黄金备份已创建!")
    print(f"   路径: {ZIP_PATH}")
    print(f"   大小: {size/1024:.1f} KB")
else:
    print(f"\n❌ 归档失败，文件未生成")
    exit(1)

# 6. 恢复运行（Softbus）
print("\n>>> 恢复 Run ...")
instance.CommunicationInterface = ECommunicationInterface.Softbus
instance.PowerOn()
time.sleep(2)
instance.Run()
time.sleep(2)
print(f"最终状态: {instance.OperatingState}")
print("\n✅ 黄金备份创建完成，实例已恢复 Softbus RUN")
