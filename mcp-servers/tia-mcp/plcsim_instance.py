"""
PLCSIM Advanced 实例管理 — 创建/停止/列举/清理/上下文管理器。

依赖 plcsim_common（加载 CLR + 共享工具函数）。
"""
import os, time, subprocess
from typing import Optional, List, Dict

from plcsim_common import (
    SimulationRuntimeManager,
    IInstance,
    ECPUType,
    EOperatingState,
    SIPSuite4,
    _decode_error,
    _resolve_cpu,
    _get_instance,
    _wait_for_state,
    _ensure_off,
    STATE_NAMES,
)


_MANAGER_EXE: Optional[str] = None  # 缓存 Runtime Manager 路径
_UI_EXE_CACHE: Optional[str] = None  # 缓存 UserInterface 路径


# ── 运行时服务管理 ──


def _ensure_runtime_manager():
    """确保 PLCSIM Advanced Runtime Manager 正在运行。

    V8.0+ 需要 Runtime Manager 进程在线才能 PowerOn 实例。
    如果未运行则启动它（安装目录下的 Manager.exe）。
    """
    global _MANAGER_EXE
    if _MANAGER_EXE is None:
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

    try:
        tasklist = subprocess.run(
            ['cmd.exe', '/c', 'tasklist', '/fi',
             'ImageName eq Siemens.Simatic.Simulation.Runtime.Manager.exe',
             '/fo', 'csv', '/nh'],
            capture_output=True, text=True, timeout=5,
            encoding='gbk', errors='replace',
        )
        if "Siemens.Simatic.Simulation.Runtime.Manager.exe" in tasklist.stdout:
            return
    except Exception:
        pass

    print(f"[plcsim] 启动 Runtime Manager ...")
    try:
        subprocess.Popen([_MANAGER_EXE], shell=True)
        time.sleep(3)
        print(f"[plcsim] Runtime Manager 已启动")
    except Exception as e:
        print(f"[plcsim] ⚠ 启动 Runtime Manager 失败: {e}")


def _ensure_user_interface():
    """确保 PLCSIM Advanced UserInterface GUI 正在运行。

    V21 TIA Portal 下载时必须能看到 PLCSIM GUI 窗口，否则扫描不到设备。
    Runtime Manager 后台服务不够，必须打开完整的 UserInterface 窗口。
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


# ── 强制清理 ──


def force_cleanup(name: str):
    """强制清理 PLCSIM 实例残留数据。

    当 PLCSIM Advanced GUI 中出现无法删除的残留实例（如 IP 显示 0.0.0.0），
    或同名实例删除后自动恢复时，使用此函数完全清理。

    清理项目:
      1. 通过 API 注销实例（UnregisterInstance）
      2. 删除该实例的持久化存储目录下的所有文件（如 plcsim_storage/*）
      3. 删除 golden backup 文件
      4. 删除 ProgramData\\Siemens\\PLCSIMADV 下的残留缓存

    Args:
        name: 实例名称（如 "factoryio"）
    """
    print(f"[plcsim] 强制清理实例 '{name}' ...")

    sp = None
    try:
        instance = _get_instance(name)
        if instance is not None:
            print(f"   API 注销 '{name}'...")
            _ensure_off(instance)
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

    known_storages = set()
    try:
        from config_loader import cfg
        known_storages.add(os.path.join(os.path.dirname(cfg.tia.project_path), "plcsim_storage"))
    except Exception:
        pass
    known_storages.add(r"D:\PLC cheng xu\TIA PLC CHENG XU\demo_V21\plcsim_storage")
    known_storages.add(r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\plcsim_storage")
    if sp:
        known_storages.add(sp)

    for sp_path in known_storages:
        if not os.path.exists(sp_path):
            continue
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
                try:
                    i = 0
                    while True:
                        sub_name = winreg.EnumKey(key, i)
                        if name.lower() in sub_name.lower():
                            sub_path = f"{subkey}\\{sub_name}"
                            winreg.DeleteKey(reg_root, sub_path)
                            print(f"   🗑 已删除注册表: {reg_desc}\\{sub_path}")
                            i -= 1
                        i += 1
                except OSError:
                    pass
                winreg.CloseKey(key)
            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"   ⚠ 注册表清理异常 {reg_desc}\\{subkey}: {e}")

    print(f"[plcsim] ✅ 强制清理完成。重启 PLCSIM Advanced GUI 后实例应完全消失。")
    print(f"   ⚠ golden backup 已被删除，需要在新建实例后重建。")


# ── 实例管理 ──


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

    cpu = _resolve_cpu(cpu_type)
    print(f"[plcsim] 注册 '{name}' CPU={cpu_type} ...")
    try:
        instance = SimulationRuntimeManager.RegisterInstance(cpu, name)
    except Exception as e:
        raise RuntimeError(f"注册 '{name}' 失败: {e}")

    try:
        if storage_path:
            os.makedirs(storage_path, exist_ok=True)
            instance.StoragePath = storage_path
            print(f"[plcsim] StoragePath = {storage_path}")

        _ensure_runtime_manager()

        print(f"[plcsim] 接口: {instance.CommunicationInterface} (V8.0 只读)")

        instance.PowerOn()
        _wait_for_state(instance, EOperatingState.Stop, timeout=20)

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


# ── 上下文管理器 ──


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
