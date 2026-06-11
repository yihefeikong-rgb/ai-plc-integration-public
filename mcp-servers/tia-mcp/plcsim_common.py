"""
PLCSIM Advanced .NET API — 共享常量与工具函数。

供 plcsim_instance.py / plcsim_backup.py / plcsim_network.py 使用。
在初次 import 此模块时加载 CLR，各子模块只需 from plcsim_common import ...。
"""
import time
from typing import Optional

_API_DLL = r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\8.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll"

# ── 模块加载后立即初始化 ──
import clr
clr.AddReference(_API_DLL)

from Siemens.Simatic.Simulation.Runtime import (
    SimulationRuntimeManager,
    IInstance,
    ECPUType,
    EOperatingState,
    ECommunicationInterface,
    SIPSuite4,
)


# ── CPU 类型快捷映射 ──
CPU_TYPES = {
    "1511": ECPUType.CPU1511,
    "1513": ECPUType.CPU1513,
    "1515": ECPUType.CPU1515,
    "1516": ECPUType.CPU1516,
    "1517": ECPUType.CPU1517,
    "1518": ECPUType.CPU1518,
    "1511f": ECPUType.CPU1511F,
    "1516f": ECPUType.CPU1516F,
}

# ── PLCSIM 错误码映射 ──
ERROR_CODES = {
    -1: "ERR_UNKNOWN",
    -14: "InstanceNotRunning",
    -30: "LicenseNotFound — PLCSIM Advanced 许可证未找到或已过期",
    -37: "ArchiveStorageNotCreated",
    -39: "InvalidOperatingState",
    -50: "VirtualSwitchMisconfigured",
    -52: "IsEmpty（无硬件配置）",
}

_LICENSE_HELP = """
╔══════════════════════════════════════════════════════════╗
║  PLCSIM Advanced 许可证问题 — Error Code: -30            ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  可能原因:                                                ║
║  1. 试用期已过（默认 14 天）                               ║
║  2. 许可证未激活                                           ║
║  3. 从 V5.0 升级后旧许可证不兼容                            ║
║                                                          ║
║  解决方案:                                                ║
║  A. 打开 PLCSIM Advanced V8.0 GUI → 检查 License/About   ║
║     确认试用期状态，必要时重新安装以刷新 14 天试用             ║
║                                                          ║
║  B. 使用 TIA Portal V18 内置 PLCSIM Basic 仿真:          ║
║     TIA Portal → 选中 PLC → Start → Start Simulation     ║
║     (无需独立 PLCSIM Advanced 许可证)                      ║
║                                                          ║
║  C. 购买 PLCSIM Advanced 正式许可证:                      ║
║     通过 Siemens 官方渠道或代理商申请                        ║
║                                                          ║
║  D. 临时方案 — 使用 OpenPLC Docker 仿真:                  ║
║     docker-compose --profile simulation up -d             ║
║     (免费，无需 Siemens 许可证)                             ║
╚══════════════════════════════════════════════════════════╝
"""

STATE_NAMES = {
    EOperatingState.InvalidOperatingState: "invalid",
    EOperatingState.Off: "off",
    EOperatingState.Booting: "booting",
    EOperatingState.Stop: "stop",
    EOperatingState.Startup: "startup",
    EOperatingState.Run: "run",
    EOperatingState.Freeze: "freeze",
    EOperatingState.ShuttingDown: "shutdown",
    EOperatingState.Hold: "hold",
}


def _decode_error(e: Exception) -> str:
    """将 PLCSIM 异常转成可读信息。"""
    msg = str(e)
    for code, desc in ERROR_CODES.items():
        if str(code) in msg:
            result = f"错误 {code}: {desc}"
            if code == -30:
                result += _LICENSE_HELP
            return result
    return msg


def _resolve_cpu(cpu: str) -> ECPUType:
    """将字符串解析为 ECPUType 枚举。"""
    cpu_lower = cpu.lower()
    if cpu_lower in CPU_TYPES:
        return CPU_TYPES[cpu_lower]
    for name in dir(ECPUType):
        if name.lower() == cpu_lower or name.lower() == f"cpu{cpu_lower}":
            return getattr(ECPUType, name)
    return ECPUType.CPU1511


def _get_instance(name: str) -> Optional[IInstance]:
    """按名称查找已注册的实例。"""
    for info in SimulationRuntimeManager.RegisteredInstanceInfo:
        if info.Name == name:
            return SimulationRuntimeManager.CreateInterface(info.ID)
    return None


def _wait_for_state(instance: IInstance, target: EOperatingState, timeout: float = 30):
    """轮询等待实例达到目标状态。"""
    start = time.time()
    while time.time() - start < timeout:
        if instance.OperatingState == target:
            return
        time.sleep(0.5)
    actual = STATE_NAMES.get(instance.OperatingState, str(instance.OperatingState))
    target_name = STATE_NAMES.get(target, str(target))
    raise TimeoutError(
        f"实例 '{instance.Name}' 在 {timeout}s 内未达到 '{target_name}'，当前: '{actual}'"
    )


def _ensure_off(instance: IInstance):
    """确保实例处于 OFF 状态。"""
    st = instance.OperatingState
    if st == EOperatingState.Off:
        return
    if st == EOperatingState.Run or st == EOperatingState.Startup:
        instance.Stop()
        _wait_for_state(instance, EOperatingState.Stop, timeout=10)
    if instance.OperatingState == EOperatingState.Stop:
        instance.PowerOff()
        _wait_for_state(instance, EOperatingState.Off, timeout=10)
