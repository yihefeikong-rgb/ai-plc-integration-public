"""
将 factory io1 从 Softbus 切换到 TCP/IP + 设 IP 10.0.0.1
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

import clr
clr.AddReference(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\5.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll")
from Siemens.Simatic.Simulation.Runtime import (
    SimulationRuntimeManager, EOperatingState, ECommunicationInterface, SIPSuite4
)

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
print(f"当前通信接口: {instance.CommunicationInterface}")

# 2. 先 Stop
print("\n>>> Stop ...")
instance.Stop()
time.sleep(2)
print(f"状态: {instance.OperatingState}")

# 3. PowerOff
print("\n>>> PowerOff ...")
instance.PowerOff()
time.sleep(2)
print(f"状态: {instance.OperatingState}")

# 4. 切换到 TCP/IP
print("\n>>> 设置通信接口 TCP/IP ...")
instance.CommunicationInterface = ECommunicationInterface.TCPIP
time.sleep(1)
print(f"通信接口: {instance.CommunicationInterface}")

# 5. PowerOn
print("\n>>> PowerOn ...")
instance.PowerOn()
time.sleep(3)
print(f"状态: {instance.OperatingState}")

# 6. 设置 IP
print("\n>>> 设置 IP 10.0.0.1 ...")
instance.SetIPSuite(0, SIPSuite4("10.0.0.1", "255.255.255.0", "0.0.0.0"), False)
time.sleep(1)
print("IP 已设置")

# 7. Run
print("\n>>> Run ...")
instance.Run()
time.sleep(3)
print(f"最终状态: {instance.OperatingState}")

if instance.OperatingState == EOperatingState.Run:
    print("\n✅ 成功！factory io1 已切换到 TCP/IP 模式")
    print(f"   IP: 10.0.0.1")
    print(f"   状态: RUN")
else:
    print(f"\n⚠️ 状态: {instance.OperatingState}")
