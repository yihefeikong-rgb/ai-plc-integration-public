"""
PLCSIM Advanced .NET API 封装 — 纯 API 操作，无需截屏/点鼠标。

用法:
    from plcsim_api import create_instance, get_instances, stop_instance

    # 创建并启动实例
    inst = create_instance("factory io1", "10.0.0.1", "255.255.255.0")

    # 查看所有已注册实例
    for info in get_instances():
        print(f"{info['name']} → {info['state']}")

    # 停止并删除
    stop_instance("factory io1")

    # 上下文管理器（自动清理）
    with PlcSimInstance("test", "10.0.0.1") as inst:
        inst.run()

依赖:
    - pythonnet (clr)
    - S7-PLCSIM Advanced V5.0
    - DLL: C:\\Program Files (x86)\\Common Files\\Siemens\\PLCSIMADV\\API\\5.0\\...
"""
import time
from typing import Optional, List, Dict

_API_DLL = r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\5.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll"

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


def _resolve_cpu(cpu: str) -> ECPUType:
    """将字符串解析为 ECPUType 枚举。"""
    cpu_lower = cpu.lower()
    if cpu_lower in CPU_TYPES:
        return CPU_TYPES[cpu_lower]
    # 尝试直接匹配枚举名
    for name in dir(ECPUType):
        if name.lower() == cpu_lower or name.lower() == f"cpu{cpu_lower}":
            return getattr(ECPUType, name)
    # 默认 1511
    return ECPUType.CPU1511


def get_instances() -> List[Dict]:
    """获取所有已注册的 PLCSIM Advanced 实例。

    Returns:
        实例列表，每个字典含: id, name, state, cpu_type
    """
    result = []
    try:
        for info in SimulationRuntimeManager.RegisteredInstanceInfo:
            instance = SimulationRuntimeManager.CreateInterface(info.ID)
            result.append({
                "id": info.ID,
                "name": info.Name,
                "state": STATE_NAMES.get(instance.OperatingState, str(instance.OperatingState)),
                "cpu_type": str(info.CPUType) if hasattr(info, 'CPUType') else "unknown",
            })
    except Exception as e:
        raise RuntimeError(f"获取实例列表失败: {e}")
    return result


def _find_instance_by_name(name: str) -> Optional[IInstance]:
    """按名称查找已注册的实例。"""
    for info in SimulationRuntimeManager.RegisteredInstanceInfo:
        if info.Name == name:
            return SimulationRuntimeManager.CreateInterface(info.ID)
    return None


def create_instance(
    name: str,
    ip: str = "10.0.0.1",
    subnet: str = "255.255.255.0",
    cpu_type: str = "1511",
    interface: str = "tcpip",
) -> IInstance:
    """创建并启动一个 PLCSIM Advanced 虚拟 PLC 实例。

    Args:
        name: 实例名称（Factory I/O 需要 "factory io1" 或 "factoryio"）
        ip: PLC IP 地址，默认 10.0.0.1
        subnet: 子网掩码，默认 255.255.255.0
        cpu_type: CPU 型号，如 "1511", "1516", "1518"，默认 1511
        interface: "tcpip" 或 "softbus"，默认 tcpip

    Returns:
        IInstance — .NET 实例对象，可调用 PowerOn/Run/Stop 等

    Raises:
        RuntimeError: 创建失败
    """
    # 1. 检查是否已存在
    existing = _find_instance_by_name(name)
    if existing is not None:
        state = STATE_NAMES.get(existing.OperatingState, "unknown")
        if state == "run":
            print(f"[plcsim] 实例 '{name}' 已在运行，复用")
            return existing
        elif state in ("stop", "off"):
            print(f"[plcsim] 实例 '{name}' 已存在（{state}），将 PowerOn")
            existing.PowerOn()
            time.sleep(2)
            existing.Run()
            _wait_for_state(existing, EOperatingState.Run, timeout=30)
            return existing
        else:
            # 状态异常，先清理再重新创建
            print(f"[plcsim] 实例 '{name}' 状态异常（{state}），先清理")
            try:
                existing.UnregisterInstance()
            except:
                pass
            time.sleep(1)

    # 2. 注册实例
    cpu = _resolve_cpu(cpu_type)
    print(f"[plcsim] 注册实例: '{name}' CPU={cpu_type} ...")
    try:
        instance = SimulationRuntimeManager.RegisterInstance(cpu, name)
    except Exception as e:
        raise RuntimeError(f"注册实例 '{name}' 失败: {e}")

    rest_ok = False
    try:
        # 3. PowerOn — 必须先通电，才能设置 IP
        print(f"[plcsim] PowerOn ...")
        instance.PowerOn()
        _wait_for_state(instance, EOperatingState.Stop, timeout=20)

        # 4. 设置通信接口和 IP（必须在 PowerOn 之后才能生效）
        if interface == "tcpip":
            instance.CommunicationInterface = ECommunicationInterface.TCPIP
            time.sleep(1)  # 等待接口切换生效
            instance.SetIPSuite(
                0,
                SIPSuite4(ip, subnet, "0.0.0.0"),
                False,  # 非保持（non-remanent）
            )
            print(f"[plcsim] 通信接口: TCPIP, IP={ip}/{subnet}")
        else:
            instance.CommunicationInterface = ECommunicationInterface.Softbus
            print(f"[plcsim] 通信接口: Softbus")

        # 5. Run
        print(f"[plcsim] Run ...")
        instance.Run()
        _wait_for_state(instance, EOperatingState.Run, timeout=30)

        # 等待一下让 PLC 初始化完成
        time.sleep(2)

        rest_ok = True
        print(f"[plcsim] ✅ 实例 '{name}' 已就绪 (IP={ip}, RUN)")
        return instance

    except Exception as e:
        # 清理失败的实例
        try:
            instance.UnregisterInstance()
        except:
            pass
        raise RuntimeError(f"创建实例 '{name}' 失败: {e}")


def stop_instance(name: str, cleanup: bool = True):
    """停止并（可选）删除实例。

    Args:
        name: 实例名称
        cleanup: True=停止后删除（Unregister），False=仅停止

    Raises:
        RuntimeError: 停止失败
    """
    instance = _find_instance_by_name(name)
    if instance is None:
        print(f"[plcsim] 实例 '{name}' 不存在，跳过")
        return

    try:
        state = STATE_NAMES.get(instance.OperatingState, "unknown")
        print(f"[plcsim] 停止实例 '{name}' (当前 {state}) ...")

        # 如果是 Run → 先 Stop
        if instance.OperatingState in (EOperatingState.Run, EOperatingState.Startup):
            instance.Stop()
            _wait_for_state(instance, EOperatingState.Stop, timeout=10)

        # PowerOff
        if instance.OperatingState in (EOperatingState.Stop,):
            instance.PowerOff()
            _wait_for_state(instance, EOperatingState.Off, timeout=10)

        if cleanup:
            print(f"[plcsim] 注销实例 '{name}' ...")
            instance.UnregisterInstance()

        print(f"[plcsim] ✅ 实例 '{name}' 已停止")
    except Exception as e:
        raise RuntimeError(f"停止实例 '{name}' 失败: {e}")


def stop_all():
    """停止并删除所有已注册实例。"""
    names = [info["name"] for info in get_instances()]
    if not names:
        print("[plcsim] 没有运行中的实例")
        return
    print(f"[plcsim] 停止所有实例: {names}")
    for name in names:
        try:
            stop_instance(name, cleanup=True)
        except Exception as e:
            print(f"[plcsim] ⚠ {name}: {e}")


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


class PlcSimInstance:
    """PLCSIM Advanced 实例上下文管理器 — with 语句自动创建/清理。

    Example:
        with PlcSimInstance("factory io1", "10.0.0.1") as inst:
            inst.write_bool("M0.0", True)   # 未来扩展
    """

    def __init__(self, name: str, ip: str = "10.0.0.1", cpu_type: str = "1511"):
        self._name = name
        self._ip = ip
        self._cpu_type = cpu_type
        self._instance: Optional[IInstance] = None

    def __enter__(self) -> "PlcSimInstance":
        self._instance = create_instance(self._name, self._ip, cpu_type=self._cpu_type)
        return self

    def __exit__(self, *args):
        if self._instance is not None:
            try:
                stop_instance(self._name, cleanup=True)
            except Exception:
                pass

    @property
    def instance(self) -> IInstance:
        return self._instance

    def run(self):
        if self._instance.OperatingState != EOperatingState.Run:
            self._instance.Run()
            _wait_for_state(self._instance, EOperatingState.Run)

    def stop(self):
        if self._instance.OperatingState == EOperatingState.Run:
            self._instance.Stop()
            _wait_for_state(self._instance, EOperatingState.Stop)


# ── CLI ──
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(__doc__)
        print("命令: list | create <name> [ip] [cpu] | stop <name> | stop-all")
        sys.exit(0)

    cmd = sys.argv[1]
    try:
        if cmd == "list":
            instances = get_instances()
            if instances:
                for i in instances:
                    print(f"  [{i['id']}] {i['name']} — {i['state']} ({i['cpu_type']})")
            else:
                print("  无运行实例")

        elif cmd == "create":
            name = sys.argv[2] if len(sys.argv) > 2 else "test"
            ip = sys.argv[3] if len(sys.argv) > 3 else "10.0.0.1"
            cpu = sys.argv[4] if len(sys.argv) > 4 else "1511"
            create_instance(name, ip, cpu_type=cpu)

        elif cmd == "stop":
            name = sys.argv[2] if len(sys.argv) > 2 else "test"
            stop_instance(name)

        elif cmd == "stop-all":
            stop_all()

        else:
            print(f"未知命令: {cmd}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)
