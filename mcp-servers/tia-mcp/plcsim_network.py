"""
PLCSIM Advanced 网络配置 — TCP/IP 切换 / 网卡绑定。

依赖 plcsim_common（加载 CLR + 共享工具函数）。
"""
import time
from typing import Optional

from plcsim_common import (
    IInstance,
    EOperatingState,
    SIPSuite4,
    SimulationRuntimeManager,
    _get_instance,
    _wait_for_state,
    STATE_NAMES,
)


def switch_to_tcpip(name: str, ip: str = "10.0.0.1", subnet: str = "255.255.255.0") -> IInstance:
    """将实例从 Softbus 切换到 TCP/IP 模式。

    Args:
        name: 实例名称
        ip: IP 地址
        subnet: 子网掩码

    Returns:
        IInstance — 切换后的实例
    """
    instance = _get_instance(name)
    if instance is None:
        raise RuntimeError(f"实例 '{name}' 不存在")

    print(f"[plcsim] 切换 '{name}' → TCP/IP {ip}/{subnet}")

    try:
        SimulationRuntimeManager.ResetNetInterfaceBindings()
        time.sleep(1)
    except Exception:
        pass

    if instance.OperatingState == EOperatingState.Run:
        instance.Stop()
        _wait_for_state(instance, EOperatingState.Stop, timeout=10)

    instance.PowerOff()
    _wait_for_state(instance, EOperatingState.Off, timeout=10)

    instance.PowerOn()
    _wait_for_state(instance, EOperatingState.Stop, timeout=20)

    try:
        instance.SetIPSuite(0, SIPSuite4(ip, subnet, "0.0.0.0"), False)
        print(f"[plcsim] IP 已设: {ip}/{subnet}")
    except Exception as e:
        print(f"[plcsim] ⚠ SetIPSuite: {e}")

    instance.Run()
    _wait_for_state(instance, EOperatingState.Run, timeout=30)
    print(f"[plcsim] OK '{name}' TCP/IP RUN")
    return instance
