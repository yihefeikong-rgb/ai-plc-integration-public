"""
列出 IInstance 上所有与存储/归档相关的方法
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import clr
clr.AddReference(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\5.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll")
from Siemens.Simatic.Simulation.Runtime import (
    SimulationRuntimeManager, EOperatingState
)

instance = None
for info in SimulationRuntimeManager.RegisteredInstanceInfo:
    if info.Name == "factory io1":
        instance = SimulationRuntimeManager.CreateInterface(info.ID)
        break

if instance is None:
    print("❌ 未找到")
    exit(1)

# 列出相关方法
print("=== IInstance 方法（存档/存储相关）===")
for m in sorted(dir(instance)):
    if any(k in m.lower() for k in ['archiv', 'storag', 'backup', 'restor', 'retriev', 'persist']):
        print(f"  {m}")

print("\n=== SimulationRuntimeManager 方法 ===")
for m in sorted(dir(SimulationRuntimeManager)):
    if any(k in m.lower() for k in ['archiv', 'storag', 'backup', 'restor', 'retriev', 'register']):
        print(f"  {m}")
