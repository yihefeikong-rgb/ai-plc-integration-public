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
    """强杀 TIA Portal 相关进程（S7*、Tia*）"""
    for filt in ['S7*', 'Tia*']:
        try:
            r = subprocess.run(
                f'tasklist /fi "IMAGENAME eq {filt}" /fo csv /nh',
                shell=True, capture_output=True, text=True,
                encoding='gbk', errors='replace')
        except Exception:
            continue
        stdout = r.stdout or ''
        for line in stdout.strip().split('\n'):
            if line:
                proc = line.replace('"', '').split(',')[0].strip()
                if proc:
                    subprocess.run(['taskkill', '/f', '/im', proc],
                                   capture_output=True)


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
    except Exception:
        _tia_dir = r'D:\TIA BEN TI\Portal V18'

    clr.AddReference(rf'{_tia_dir}\PublicAPI\V18\Siemens.Engineering.dll')
    clr.AddReference(rf'{_tia_dir}\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode
    from System.IO import FileInfo

    tia_mode = TiaPortalMode.WithUserInterface if mode == "gui" else TiaPortalMode.WithoutUserInterface
    tia = TiaPortal(tia_mode)
    project = None

    try:
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
