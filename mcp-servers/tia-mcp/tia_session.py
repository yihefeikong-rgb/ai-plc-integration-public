"""
TIA Portal 会话管理器 — 确保每次连接都正确关闭，防止进程泄漏。

用法:
    from tia_session import tia_session

    # 基本用法：自动 Open → Dispose
    with tia_session() as (project, plc_sw):
        # project: TIA Project 对象
        # plc_sw: PlcSoftware 对象（自动查找）
        ...

    # 指定项目路径
    with tia_session("D:\\path\\to\\project.ap18") as (project, plc_sw):
        ...

    # GUI 模式（下载用）
    with tia_session(mode="gui") as (project, plc_sw):
        ...
"""
import subprocess
import time
import gc
from contextlib import contextmanager
from pathlib import Path


def _kill_tia_processes():
    """清理残留的 headless TIA Portal 进程（仅杀无窗口的 headless 实例）

    注意：不能杀 S7* / Siemens* 等系统进程，会误杀 PLCSIM 和 GUI 实例。
    只杀通过 tasklist 可以用窗口标题区分的 headless TIA Portal 进程。
    """
    try:
        r = subprocess.run(
            'tasklist /fi "IMAGENAME eq Siemens.Automation.Portal.exe" /fo csv /nh',
            shell=True, capture_output=True, text=True,
            encoding='gbk', errors='replace',
        )
        if not r.stdout:
            return
        for line in r.stdout.strip().split('\n'):
            if line and 'Siemens.Automation.Portal.exe' in line:
                parts = line.replace('"', '').split(',')
                if len(parts) >= 2:
                    pid = parts[1].strip()
                    # 检查该进程有无主窗口（有窗口的是 GUI 实例，不能杀）
                    try:
                        check = subprocess.run(
                            f'tasklist /fi "PID eq {pid}" /fi "WINDOWTITLE ne n/a" /fo csv /nh',
                            shell=True, capture_output=True, text=True,
                            encoding='gbk', errors='replace',
                        )
                        if check.stdout and check.stdout.strip():
                            continue  # 有窗口，跳过
                        subprocess.run(['taskkill', '/f', '/pid', pid],
                                       capture_output=True)
                    except Exception:
                        pass
    except Exception:
        pass


def _find_plc_software(project):
    """从 TIA 项目中查找 PlcSoftware 对象"""
    try:
        from Siemens.Engineering.HW.Features import SoftwareContainer
    except ImportError:
        return None
    for device in project.Devices:
        for item in device.DeviceItems:
            try:
                c = item.GetService[SoftwareContainer]()
                if c and c.Software and 'PlcSoftware' in c.Software.GetType().FullName:
                    return c.Software
            except Exception:
                pass
    return None


@contextmanager
def tia_session(project_path: str = None, mode: str = "headless"):
    """TIA Portal 会话上下文管理器。

    Args:
        project_path: TIA 项目 .ap18 路径，留空从 config.yaml 读取
        mode: "headless" (无界面) 或 "gui" (有界面，用于下载到 PLCSIM)

    Yields:
        (project, plc_sw) 元组 — TIA Project 和 PlcSoftware 对象

    Example:
        with tia_session() as (project, plc):
            plc.BlockGroup.Blocks.Import(...)
            compiler = plc.GetService[ICompilable]()
            compiler.Compile()
            project.Save()
    """
    import clr

    # 解析项目路径
    if not project_path:
        try:
            from config_loader import cfg
            project_path = cfg.tia.project_path
        except Exception:
            raise ValueError("未指定 project_path 且无法从 config.yaml 读取")

    # 加载 TIA Openness DLL
    try:
        from config_loader import cfg
        _tia_dir = cfg.tia.install_dir
        _tia_ver = cfg.tia.version
    except Exception:
        _tia_dir = r'D:\TIA BEN TI\Portal V18'
        _tia_ver = 'V18'

    clr.AddReference(rf'{_tia_dir}\PublicAPI\{_tia_ver}\Siemens.Engineering.dll')
    clr.AddReference(rf'{_tia_dir}\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode
    from System.IO import FileInfo

    tia_mode = TiaPortalMode.WithUserInterface if mode == "gui" else TiaPortalMode.WithoutUserInterface
    tia = TiaPortal(tia_mode)
    project = None

    try:
        # 先找已打开的项目，避免 "项目已被打开" 错误
        project = None
        for p in tia.Projects:
            try:
                if p.Path.Path == project_path:
                    project = p
                    print(f'   ℹ 使用已打开的项目: {p.Name}')
                    break
            except Exception:
                continue
        if project is None:
            project = tia.Projects.Open(FileInfo(project_path))
        plc_sw = _find_plc_software(project)
        yield (project, plc_sw)
    finally:
        try:
            if project:
                project.Save()
        except Exception:
            pass
        try:
            tia.Dispose()
        except Exception:
            pass
        try:
            import gc as _gc
            _gc.collect()
        except Exception:
            pass
        if mode == "headless":
            time.sleep(1)
            _kill_tia_processes()
