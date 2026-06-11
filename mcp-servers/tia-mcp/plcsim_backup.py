"""
PLCSIM Advanced 备份与恢复 — 归档/还原黄金备份 (ZIP)。

依赖 plcsim_common（加载 CLR + 共享工具函数）。
"""
import os, time
from typing import Optional

from plcsim_common import (
    IInstance,
    EOperatingState,
    SIPSuite4,
    SimulationRuntimeManager,
    _decode_error,
    _resolve_cpu,
    _get_instance,
    _wait_for_state,
    _ensure_off,
    STATE_NAMES,
)
from plcsim_instance import _ensure_runtime_manager, stop_instance


def archive_instance(name: str, zip_path: str, storage_path: Optional[str] = None) -> str:
    """将已配置实例归档为 ZIP（黄金备份）。

    流程: 当前状态 → Stop → PowerOff → ArchiveStorage

    Args:
        name: 实例名称
        zip_path: 输出的 ZIP 完整路径
        storage_path: 可选，设置持久化存储路径

    Returns:
        创建的 ZIP 路径

    Raises:
        RuntimeError: 归档失败
    """
    instance = _get_instance(name)
    if instance is None:
        raise RuntimeError(f"实例 '{name}' 不存在")

    print(f"[plcsim] 归档 '{name}' → {zip_path}")

    _ensure_off(instance)

    if storage_path:
        os.makedirs(storage_path, exist_ok=True)
        instance.StoragePath = storage_path

    zip_dir = os.path.dirname(zip_path)
    if zip_dir:
        os.makedirs(zip_dir, exist_ok=True)

    try:
        instance.ArchiveStorage(zip_path)
    except Exception as e:
        raise RuntimeError(f"ArchiveStorage 失败: {e}")

    if not os.path.exists(zip_path):
        raise RuntimeError(f"归档文件未生成: {zip_path}")

    size_kb = os.path.getsize(zip_path) / 1024
    print(f"[plcsim] OK 归档完成: {zip_path} ({size_kb:.1f} KB)")
    return zip_path


def restore_instance(
    name: str,
    golden_zip: str,
    storage_path: str,
    ip: str = "192.168.0.1",
    subnet: str = "255.255.255.0",
    cpu_type: str = "1511",
    interface: str = "tcpip",
    auto_run: bool = True,
) -> IInstance:
    """从黄金备份恢复实例（替代 TIA Portal 手动下载）。

    默认为 TCP/IP 模式 + 192.168.0.1，适用于 Factory I/O S7-1200/1500 驱动连接。

    流程:
        RegisterInstance → StoragePath → RetrieveStorage
        → PowerOn → SetIP (if tcpip) → Run

    Args:
        name: 新实例名称
        golden_zip: 黄金备份 ZIP 路径
        storage_path: 持久化存储目录（必须，否则 RetrieveStorage 失败）
        ip: PLC IP 地址
        subnet: 子网掩码
        cpu_type: CPU 型号（必须匹配备份时的型号）
        interface: "softbus" 或 "tcpip"

    Returns:
        IInstance — 运行中的实例

    Raises:
        RuntimeError: 恢复失败
    """
    if not os.path.exists(golden_zip):
        raise RuntimeError(f"黄金备份文件不存在: {golden_zip}")

    existing = _get_instance(name)
    if existing is not None:
        stop_instance(name, cleanup=True)
        time.sleep(1)

    cpu = _resolve_cpu(cpu_type)
    print(f"[plcsim] 注册 '{name}' CPU={cpu_type} ...")
    instance = SimulationRuntimeManager.RegisterInstance(cpu, name)

    try:
        os.makedirs(storage_path, exist_ok=True)
        instance.StoragePath = storage_path
        print(f"[plcsim] StoragePath = {storage_path}")

        print(f"[plcsim] RetrieveStorage ← {golden_zip}")
        instance.RetrieveStorage(golden_zip)
        time.sleep(1)

        try:
            golden_interface = instance.CommunicationInterface
        except Exception:
            golden_interface = None
        interface_lower = interface.lower()

        if interface_lower == "tcpip":
            try:
                SimulationRuntimeManager.ResetNetInterfaceBindings()
                time.sleep(1)
            except Exception:
                print(f"[plcsim] ⚠ ResetNetInterfaceBindings 不可用，跳过")

        _ensure_runtime_manager()
        instance.PowerOn()
        _wait_for_state(instance, EOperatingState.Stop, timeout=20)

        if interface_lower == "tcpip":
            try:
                instance.SetIPSuite(0, SIPSuite4(ip, subnet, "0.0.0.0"), False)
                print(f"[plcsim] TCPIP {ip}/{subnet}")
            except Exception as e:
                print(f"[plcsim] ⚠ SetIPSuite: {e}")
        else:
            print(f"[plcsim] Softbus（来自 golden 备份）")

        if auto_run:
            instance.Run()
            _wait_for_state(instance, EOperatingState.Run, timeout=30)
            time.sleep(2)
            print(f"[plcsim] OK 恢复完成: '{name}' RUN (IP={ip})")
        else:
            print(f"[plcsim] OK 恢复完成: '{name}' STOP (待下载状态，黄色)")
        return instance

    except Exception as e:
        decoded = _decode_error(e)
        try:
            instance.UnregisterInstance()
        except:
            pass
        raise RuntimeError(f"恢复实例 '{name}' 失败: {decoded}")
