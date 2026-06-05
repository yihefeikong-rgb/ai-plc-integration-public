"""
TCP/IP fix v2 — 正确绑定虚拟网卡
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

import clr
clr.AddReference(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\5.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll")
from Siemens.Simatic.Simulation.Runtime import (
    SimulationRuntimeManager, EOperatingState, ECommunicationInterface,
    SIPSuite4, ECPUType
)

# 查看所有网卡
print("=== 可用网卡 ===")
plcsim_idx = None
for iface in SimulationRuntimeManager.NetInterfaces:
    mac = iface.MACAddress
    desc = iface.interfaceDescription
    idx = iface.interfaceIndex
    is_con = iface.isConnected
    vsw = iface.vSwitchBindingEnabled
    print(f"  [{idx}] {mac}  {desc}  (up={is_con}, vSwitch={vsw})")
    if "PLCSIM" in desc:
        plcsim_idx = idx

if plcsim_idx:
    print(f"\n✅ 找到 PLCSIM 虚拟网卡: ID={plcsim_idx}")
else:
    print("\n❌ 未找到 PLCSIM 虚拟网卡")

# 尝试 SetNetInterfaceBindings — 找一下实际的方法名
print("\n=== 搜索网卡绑定方法 ===")
for m in sorted(dir(SimulationRuntimeManager)):
    if 'interface' in m.lower() or 'net' in m.lower() or 'switch' in m.lower() or 'bind' in m.lower():
        print(f"  {m}")

# 看看有没有别的方式设置网卡
# 可能是属性而不是方法
print("\n=== 网卡属性 ===")
# ResetNetInterfaceBindings 看起来可用
# 先重置再绑定
try:
    print("重置网卡绑定...")
    SimulationRuntimeManager.ResetNetInterfaceBindings()
    print("  ✅ 重置成功")
except Exception as e:
    print(f"  ❌ 重置失败: {e}")

import time
time.sleep(1)

# 现在创建实例试 TCP/IP
print("\n=== 创建 TCP/IP 实例 ===")
instance = SimulationRuntimeManager.RegisterInstance(ECPUType.CPU1511, "test_tcpip2")
try:
    storage = os.path.join(os.path.dirname(__file__), "test_storage")
    os.makedirs(storage, exist_ok=True)
    instance.StoragePath = storage
    
    instance.CommunicationInterface = ECommunicationInterface.TCPIP
    time.sleep(1)
    print(f"  接口: {instance.CommunicationInterface}")
    
    instance.PowerOn()
    time.sleep(3)
    print(f"  PowerOn: {instance.OperatingState}")
    
    if instance.OperatingState == EOperatingState.Stop:
        instance.SetIPSuite(0, SIPSuite4("10.0.0.55", "255.255.255.0", "0.0.0.0"), False)
        print("  IP: 10.0.0.55")
        
        instance.Run()
        time.sleep(3)
        
        if instance.OperatingState == EOperatingState.Run:
            print("\n✅ TCP/IP 模式成功！")
        else:
            print(f"\n⚠️ 状态: {instance.OperatingState}")
    else:
        print(f"⚠️ Stop 状态未达到: {instance.OperatingState}")
        
except Exception as e:
    print(f"\n❌ {e}")
finally:
    try:
        instance.PowerOff()
        time.sleep(1)
        instance.UnregisterInstance()
        print("已清理")
    except:
        pass
