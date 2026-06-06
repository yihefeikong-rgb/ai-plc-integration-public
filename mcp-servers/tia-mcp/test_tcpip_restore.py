"""
全流程测试：Restore + TCP/IP 模式
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

GOLDEN = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\factory_io1_golden.zip"
STORAGE = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\plcsim_storage"

if not os.path.exists(GOLDEN):
    print(f"❌ golden.zip 不存在: {GOLDEN}")
    sys.exit(1)

import clr
clr.AddReference(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\5.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll")
from Siemens.Simatic.Simulation.Runtime import SimulationRuntimeManager

# 先重置网卡
SimulationRuntimeManager.ResetNetInterfaceBindings()
print("✅ 网卡绑定已重置")

from plcsim_api import restore_instance, stop_instance, get_instances

try:
    inst = restore_instance(
        name="factory_io1",
        golden_zip=GOLDEN,
        storage_path=STORAGE,
        ip="192.168.0.1",
        cpu_type="1511",
        interface="tcpip",  # ← TCP/IP 模式！
    )
    print(f"\n✅ 最终状态: {inst.OperatingState}")
except Exception as e:
    print(f"\n❌ 失败: {e}")
