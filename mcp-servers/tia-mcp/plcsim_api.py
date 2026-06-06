"""
PLCSIM Advanced .NET API 封装 — 纯 API 操作，无需截屏/点鼠标。

用法:
    from plcsim_api import create_instance, get_instances, stop_instance

    # 创建并启动实例
    inst = create_instance("factory io1", "10.0.0.1", "255.255.255.0")

    # 从黄金备份克隆
    restore_instance("new_plc", "golden.zip", "D:\\persist\\new_plc", "10.0.0.2")

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
    - S7-PLCSIM Advanced V8.0（向后兼容 V5.0+）
    - DLL: C:\\Program Files (x86)\\Common Files\\Siemens\\PLCSIMADV\\API\\8.0\\...
"""
import time, os, subprocess
from typing import Optional, List, Dict

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


def _decode_error(e: Exception) -> str:
    """将 PLCSIM 异常转成可读信息。"""
    msg = str(e)
    for code, desc in ERROR_CODES.items():
        if str(code) in msg:
            result = f"错误 {code}: {desc}"
            # 许可证错误附带详细帮助
            if code == -30:
                result += _LICENSE_HELP
            return result
    return msg


_MANAGER_EXE = None  # 缓存 Runtime Manager 路径
_UI_EXE = None  # 缓存 UserInterface 路径


def _ensure_runtime_manager():
    """确保 PLCSIM Advanced Runtime Manager 正在运行。

    V8.0+ 需要 Runtime Manager 进程在线才能 PowerOn 实例。
    如果未运行则启动它（安装目录下的 Manager.exe）。
    """
    # [existing code unchanged below]
    global _MANAGER_EXE
    if _MANAGER_EXE is None:
        # 搜索路径：config.yaml 配置路径 → Common Files 路径
        try:
            from config_loader import cfg
            adv_dir = cfg.simulation.advanced_install_dir
            mgr_in_adv = os.path.join(adv_dir, 'bin', 'Siemens.Simatic.Simulation.Runtime.Manager.exe')
        except Exception:
            adv_dir = None
            mgr_in_adv = None

        common = r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV"
        candidates = []
        if mgr_in_adv:
            candidates.append(mgr_in_adv)
        candidates += [
            os.path.join(common, "Siemens.Simatic.Simulation.Runtime.Manager.exe"),
            os.path.join(common, "Simulation.Runtime.Manager.exe"),
        ]
        for c in candidates:
            if c and os.path.exists(c):
                _MANAGER_EXE = c
                break
        if _MANAGER_EXE is None:
            print("[plcsim] ⚠ PLCSIM Runtime Manager 未找到，跳过自动启动")
            print("[plcsim]   搜索路径: " + " ; ".join(c for c in candidates if c))
            return

    # 检查是否已在运行（使用 cmd.exe /c 避免 Git Bash 参数转发）
    try:
        tasklist = subprocess.run(
            ['cmd.exe', '/c', 'tasklist', '/fi',
             'ImageName eq Siemens.Simatic.Simulation.Runtime.Manager.exe',
             '/fo', 'csv', '/nh'],
            capture_output=True, text=True, timeout=5,
            encoding='gbk', errors='replace',
        )
        if "Siemens.Simatic.Simulation.Runtime.Manager.exe" in tasklist.stdout:
            return  # 已运行
    except Exception:
        pass

    print(f"[plcsim] 启动 Runtime Manager ...")
    try:
        subprocess.Popen([_MANAGER_EXE], shell=True)
        time.sleep(3)
        print(f"[plcsim] Runtime Manager 已启动")
    except Exception as e:
        print(f"[plcsim] ⚠ 启动 Runtime Manager 失败: {e}")


_UI_EXE_CACHE = None


def force_cleanup(name: str):
    """强制清理 PLCSIM 实例残留数据。

    当 PLCSIM Advanced GUI 中出现无法删除的残留实例（如 IP 显示 0.0.0.0），
    或同名实例删除后自动恢复时，使用此函数完全清理。

    ⚠ 注意：这会同时删除 PLCSIM 实例对应的 golden backup 文件（如果有）。

    清理项目:
      1. 通过 API 注销实例（UnregisterInstance）
      2. 删除该实例的持久化存储目录下的所有文件（如 plcsim_storage/*）
      3. 删除 golden backup 文件
      4. 删除 ProgramData\\Siemens\\PLCSIMADV 下的残留缓存

    Args:
        name: 实例名称（如 "factoryio"）
    """
    print(f"[plcsim] 强制清理实例 '{name}' ...")

    # 1. API 注销
    sp = None
    try:
        instance = _get_instance(name)
        if instance is not None:
            print(f"   API 注销 '{name}'...")
            _ensure_off(instance)
            # 先读取 StoragePath（用于后续清理）
            try:
                sp = instance.StoragePath
                if sp:
                    print(f"   实例存储路径: {sp}")
            except Exception:
                sp = None
            instance.UnregisterInstance()
            print(f"   ✅ 已 API 注销")
    except Exception as e:
        print(f"   ⚠ API 注销异常（可忽略）: {e}")
        sp = None

    # 2. 清理持久化存储目录（PLCSIM 实例数据直接存在根下，不是子目录！）
    known_storages = set()
    try:
        from config_loader import cfg
        known_storages.add(os.path.join(os.path.dirname(cfg.tia.project_path), "plcsim_storage"))
    except Exception:
        pass
    known_storages.add(r"D:\PLC cheng xu\TIA PLC CHENG XU\demo_V21\plcsim_storage")
    known_storages.add(r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\plcsim_storage")
    # 如果 API 返回了 StoragePath 也加上
    if sp:
        known_storages.add(sp)

    for sp_path in known_storages:
        if not os.path.exists(sp_path):
            continue
        # 这个目录就是该实例的完整持久化数据，全部删除
        import shutil
        for entry in os.listdir(sp_path):
            entry_path = os.path.join(sp_path, entry)
            try:
                if os.path.isfile(entry_path):
                    os.remove(entry_path)
                else:
                    shutil.rmtree(entry_path, ignore_errors=True)
                print(f"   🗑 已删除: {entry_path}")
            except Exception as e:
                print(f"   ⚠ 删除失败 {entry_path}: {e}")

    # 3. 删除 golden backup 文件
    known_goldens = [
        os.path.join(os.path.dirname(p), f"factory_io1_golden.zip") for p in known_storages
    ] + [
        r"D:\PLC cheng xu\TIA PLC CHENG XU\demo_V21\factory_io1_golden.zip",
        r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\factory_io1_golden.zip",
    ]
    for gz in known_goldens:
        if gz and os.path.exists(gz):
            try:
                os.remove(gz)
                print(f"   🗑 已删除 golden: {gz}")
            except Exception as e:
                print(f"   ⚠ 删除 golden 失败 {gz}: {e}")

    # 4. 清理 ProgramData 下的实例缓存
    progdata = r"C:\ProgramData\Siemens\PLCSIMADV"
    if os.path.exists(progdata):
        for entry in os.listdir(progdata):
            if name.lower() in entry.lower() or f"_{name}" in entry:
                entry_path = os.path.join(progdata, entry)
                try:
                    if os.path.isfile(entry_path):
                        os.remove(entry_path)
                    else:
                        import shutil
                        shutil.rmtree(entry_path, ignore_errors=True)
                    print(f"   🗑 已清理 ProgramData: {entry_path}")
                except Exception as e:
                    print(f"   ⚠ 清理失败: {e}")

    # 4. 清理注册表中的实例记录
    # PLCSIM Advanced 会在注册表中缓存实例列表，导致 GUI 重启后仍然显示
    import winreg
    for reg_root, reg_desc in [
        (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
        (winreg.HKEY_CURRENT_USER, "HKCU"),
    ]:
        for subkey in [
            r"SOFTWARE\Siemens\PLCSIMADV\RegisteredInstances",
            r"SOFTWARE\Siemens\PLCSIMADV\Instances",
            r"SOFTWARE\Siemens\PLCSIMADV",
        ]:
            try:
                key = winreg.OpenKey(reg_root, subkey, 0, winreg.KEY_ALL_ACCESS)
                # 枚举子项删包含 name 的
                try:
                    i = 0
                    while True:
                        sub_name = winreg.EnumKey(key, i)
                        if name.lower() in sub_name.lower():
                            sub_path = f"{subkey}\\{sub_name}"
                            winreg.DeleteKey(reg_root, sub_path)
                            print(f"   🗑 已删除注册表: {reg_desc}\\{sub_path}")
                            i -= 1  # 删除后索引前移
                        i += 1
                except OSError:
                    pass  # 枚举结束
                winreg.CloseKey(key)
            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"   ⚠ 注册表清理异常 {reg_desc}\\{subkey}: {e}")

    print(f"[plcsim] ✅ 强制清理完成。重启 PLCSIM Advanced GUI 后实例应完全消失。")
    print(f"   ⚠ golden backup 已被删除，需要在新建实例后重建。")


def _ensure_user_interface():
    """确保 PLCSIM Advanced UserInterface GUI 正在运行。

    V21 TIA Portal 下载时必须能看到 PLCSIM GUI 窗口，否则扫描不到设备。
    Runtime Manager 后台服务不够，必须打开完整的 UserInterface 窗口。
    注意：先启动 UserInterface，它会自动连带确保 Runtime Manager 运行。
    """
    global _UI_EXE_CACHE
    if _UI_EXE_CACHE is None:
        try:
            from config_loader import cfg
            adv_dir = cfg.simulation.advanced_install_dir
            ui_candidate = os.path.join(adv_dir, 'bin', 'Siemens.Simatic.PlcSim.Advanced.UserInterface.exe')
        except Exception:
            adv_dir = None
            ui_candidate = None

        install_root = r"D:\TIA FANG ZHEN\PLCSIMADV"
        candidates = []
        if ui_candidate and os.path.exists(ui_candidate):
            candidates.append(ui_candidate)
        candidates += [
            os.path.join(install_root, 'bin', 'Siemens.Simatic.PlcSim.Advanced.UserInterface.exe'),
            os.path.join(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV",
                         "Siemens.Simatic.PlcSim.Advanced.UserInterface.exe"),
        ]
        for c in candidates:
            if c and os.path.exists(c):
                _UI_EXE_CACHE = c
                break
        if _UI_EXE_CACHE is None:
            print("[plcsim] ⚠ PLCSIM UserInterface 未找到，跳过 GUI 启动")
            print("[plcsim]   搜索路径: " + " ; ".join(c for c in candidates if c))
            return

    # 检查是否已在运行
    try:
        tasklist = subprocess.run(
            ['cmd.exe', '/c', 'tasklist', '/fi',
             'ImageName eq Siemens.Simatic.PlcSim.Advanced.UserInterface.exe',
             '/fo', 'csv', '/nh'],
            capture_output=True, text=True, timeout=5,
            encoding='gbk', errors='replace',
        )
        if "Siemens.Simatic.PlcSim.Advanced.UserInterface.exe" in tasklist.stdout:
            print("[plcsim] ✅ PLCSIM GUI 已在运行")
            return
    except Exception:
        pass

    print("[plcsim] 🚀 启动 PLCSIM Advanced GUI (UserInterface)...")
    try:
        subprocess.Popen([_UI_EXE_CACHE], shell=True)
        time.sleep(5)
        print("[plcsim] ✅ PLCSIM GUI 已启动（设备可被 V21 扫描）")
    except Exception as e:
        print(f"[plcsim] ⚠ 启动 PLCSIM GUI 失败: {e}")


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


# ── 公开 API ──


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


def create_instance(
    name: str,
    ip: str = "192.168.0.1",
    subnet: str = "255.255.255.0",
    cpu_type: str = "1511",
    interface: str = "tcpip",
    storage_path: Optional[str] = None,
) -> IInstance:
    """创建并启动一个 PLCSIM Advanced 虚拟 PLC 实例（空壳 CPU，无硬件配置）。

    默认为 TCP/IP 模式 + 192.168.0.1，适用于 Factory I/O 通过 S7-1200/1500 驱动连接。

    Args:
        name: 实例名称
        ip: PLC IP 地址
        subnet: 子网掩码
        cpu_type: CPU 型号
        interface: "tcpip" 或 "softbus"
        storage_path: 持久化存储路径（设了才能 ArchiveStorage）

    Returns:
        IInstance — .NET 实例对象

    Raises:
        RuntimeError: 创建失败
    """
    # 检查是否已存在
    existing = _get_instance(name)
    if existing is not None:
        st = STATE_NAMES.get(existing.OperatingState, "unknown")
        if st == "run":
            print(f"[plcsim] 实例 '{name}' 已在运行，复用")
            return existing
        elif st in ("stop", "off"):
            print(f"[plcsim] 实例 '{name}' 已存在（{st}），恢复运行")
            existing.PowerOn()
            time.sleep(2)
            existing.Run()
            _wait_for_state(existing, EOperatingState.Run, timeout=30)
            return existing
        else:
            print(f"[plcsim] 实例 '{name}' 状态异常（{st}），重建")
            try:
                _ensure_off(existing)
                existing.UnregisterInstance()
            except:
                pass
            time.sleep(1)

    # 注册实例
    cpu = _resolve_cpu(cpu_type)
    print(f"[plcsim] 注册 '{name}' CPU={cpu_type} ...")
    try:
        instance = SimulationRuntimeManager.RegisterInstance(cpu, name)
    except Exception as e:
        raise RuntimeError(f"注册 '{name}' 失败: {e}")

    try:
        # 设持久化路径（必须在 PowerOn 前）
        if storage_path:
            os.makedirs(storage_path, exist_ok=True)
            instance.StoragePath = storage_path
            print(f"[plcsim] StoragePath = {storage_path}")

        _ensure_runtime_manager()

        # V8.0 中 CommunicationInterface 注册后即只读（默认 Softbus）
        # 如需 TCP/IP，只能通过调用 SetIPSuite 后 TIA Portal 经虚拟网卡连接
        print(f"[plcsim] 接口: {instance.CommunicationInterface} (V8.0 只读)")

        instance.PowerOn()
        _wait_for_state(instance, EOperatingState.Stop, timeout=20)

        # 设 IP（TCP/IP 模式，必须在 PowerOn 后、Run 前）
        if interface == "tcpip":
            instance.SetIPSuite(0, SIPSuite4(ip, subnet, "0.0.0.0"), False)
            print(f"[plcsim] TCPIP {ip}/{subnet}")
        else:
            print(f"[plcsim] Softbus（默认）")

        instance.Run()
        _wait_for_state(instance, EOperatingState.Run, timeout=30)
        time.sleep(2)
        print(f"[plcsim] OK '{name}' RUN (IP={ip})")
        return instance

    except Exception as e:
        decoded = _decode_error(e)
        try:
            instance.UnregisterInstance()
        except:
            pass
        raise RuntimeError(f"创建 '{name}' 失败: {decoded}")


def stop_instance(name: str, cleanup: bool = True):
    """停止并（可选）删除实例。"""
    instance = _get_instance(name)
    if instance is None:
        print(f"[plcsim] 实例 '{name}' 不存在，跳过")
        return
    try:
        st = STATE_NAMES.get(instance.OperatingState, "unknown")
        print(f"[plcsim] 停止 '{name}' ({st}) ...")
        _ensure_off(instance)
        if cleanup:
            instance.UnregisterInstance()
            print(f"[plcsim] OK '{name}' 已注销")
        else:
            print(f"[plcsim] OK '{name}' 已停止")
    except Exception as e:
        raise RuntimeError(f"停止 '{name}' 失败: {e}")


def stop_all():
    """停止并删除所有已注册实例。"""
    names = [info["name"] for info in get_instances()]
    if not names:
        print("[plcsim] 没有运行中的实例")
        return
    print(f"[plcsim] 停止所有: {names}")
    for name in names:
        try:
            stop_instance(name, cleanup=True)
        except Exception as e:
            print(f"[plcsim] ⚠ {name}: {e}")


# ── Archive / Restore（黄金备份核心）──


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

    # 删除已存在的同名实例
    existing = _get_instance(name)
    if existing is not None:
        stop_instance(name, cleanup=True)
        time.sleep(1)

    cpu = _resolve_cpu(cpu_type)
    print(f"[plcsim] 注册 '{name}' CPU={cpu_type} ...")
    instance = SimulationRuntimeManager.RegisterInstance(cpu, name)

    try:
        # 设持久化路径（关键：必须在 RetrieveStorage 前）
        os.makedirs(storage_path, exist_ok=True)
        instance.StoragePath = storage_path
        print(f"[plcsim] StoragePath = {storage_path}")

        # 恢复硬件配置
        print(f"[plcsim] RetrieveStorage ← {golden_zip}")
        instance.RetrieveStorage(golden_zip)
        time.sleep(1)

        # 读取 golden 备份中的通信接口（V8.0 中完全只读，仅用于显示）
        try:
            golden_interface = instance.CommunicationInterface
        except Exception:
            golden_interface = None
        interface_lower = interface.lower()
        target_comm = ECommunicationInterface.TCPIP if interface_lower == "tcpip" else ECommunicationInterface.Softbus

        # V8.0 中 CommunicationInterface 只读，SetIPSuite 自动启用 TCP/IP 监听
        if interface_lower == "tcpip":
            try:
                SimulationRuntimeManager.ResetNetInterfaceBindings()
                time.sleep(1)
            except Exception:
                print(f"[plcsim] ⚠ ResetNetInterfaceBindings 不可用，跳过")

        # 起机
        _ensure_runtime_manager()
        instance.PowerOn()
        _wait_for_state(instance, EOperatingState.Stop, timeout=20)

        # 设 IP（TCP/IP 模式）
        if interface_lower == "tcpip":
            try:
                instance.SetIPSuite(0, SIPSuite4(ip, subnet, "0.0.0.0"), False)
                print(f"[plcsim] TCPIP {ip}/{subnet}")
            except Exception as e:
                print(f"[plcsim] ⚠ SetIPSuite: {e}")
        else:
            print(f"[plcsim] Softbus（来自 golden 备份）")

        # Run（V21 下载前需保持 STOP 状态，黄色；下载后才变 RUN）
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

    # 重置网卡绑定（解决 VirtualSwitchMisconfigured）
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

    # V8.0 中 CommunicationInterface 只读，SetIPSuite 即启用 TCP/IP
    # 跳过 interface 赋值，直接调用 SetIPSuite

    # 起机
    instance.PowerOn()
    _wait_for_state(instance, EOperatingState.Stop, timeout=20)

    # 设 IP
    try:
        instance.SetIPSuite(0, SIPSuite4(ip, subnet, "0.0.0.0"), False)
        print(f"[plcsim] IP 已设: {ip}/{subnet}")
    except Exception as e:
        print(f"[plcsim] ⚠ SetIPSuite: {e}")

    instance.Run()
    _wait_for_state(instance, EOperatingState.Run, timeout=30)
    print(f"[plcsim] OK '{name}' TCP/IP RUN")
    return instance


class PlcSimInstance:
    """PLCSIM Advanced 实例上下文管理器 — with 语句自动创建/清理。

    Example:
        with PlcSimInstance("factory io1", "10.0.0.1") as inst:
            inst.run()
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

    def _usage():
        print(__doc__)
        print("命令:")
        print("  list                         列出实例")
        print("  create <name> [ip] [cpu]     创建空壳实例")
        print("  stop <name>                  停止+删除实例")
        print("  stop-all                     停止所有")
        print("  purge <name>                 强制清理残留实例数据")
        print("  archive <name> <zip>         归档为 ZIP（黄金备份）")
        print("  restore <name> <zip> <sp>    从 ZIP 恢复")
        print("  tcpip <name> <ip>            切换到 TCP/IP")
        sys.exit(0)

    if len(sys.argv) < 2:
        _usage()

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
            ip = sys.argv[3] if len(sys.argv) > 3 else "192.168.0.1"
            cpu = sys.argv[4] if len(sys.argv) > 4 else "1511"
            create_instance(name, ip, cpu_type=cpu)

        elif cmd == "stop":
            stop_instance(sys.argv[2])

        elif cmd == "stop-all":
            stop_all()

        elif cmd == "purge":
            force_cleanup(sys.argv[2])

        elif cmd == "archive":
            name = sys.argv[2]
            zip_path = sys.argv[3]
            archive_instance(name, zip_path)

        elif cmd == "restore":
            name = sys.argv[2]
            zip_path = sys.argv[3]
            sp = sys.argv[4]
            ip = sys.argv[5] if len(sys.argv) > 5 else "192.168.0.1"
            restore_instance(name, zip_path, sp, ip)

        elif cmd == "tcpip":
            name = sys.argv[2]
            ip = sys.argv[3] if len(sys.argv) > 3 else "192.168.0.1"
            switch_to_tcpip(name, ip)

        else:
            print(f"未知命令: {cmd}")
            _usage()
    except Exception as e:
        msg = str(e)
        if "-30" in msg or "LicenseNotFound" in msg:
            print(f"ERR: {msg}")
            print(_LICENSE_HELP)
        else:
            decoded = _decode_error(e)
            print(f"ERR: {decoded}")
        sys.exit(1)
