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
            ['cmd.exe', '/c', 'tasklist', '/fi', 'IMAGENAME eq Siemens.Automation.Portal.exe', '/fo', 'csv', '/nh'],
            capture_output=True, text=True,
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
                            ['cmd.exe', '/c', 'tasklist', '/fi', f'PID eq {pid}', '/fi', 'WINDOWTITLE ne n/a', '/fo', 'csv', '/nh'],
                            capture_output=True, text=True,
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


def ensure_service_initialized(timeout_sec: int = 120) -> bool:
    """确保 TIA Portal 后台服务已初始化，headless 连接可用。

    TIA Portal Openness WithoutUserInterface 模式需要 IPC 通道。
    该通道在第一次 GUI 启动后自动初始化且保持存活。
    如果 headless 连接失败，启动 GUI 来初始化服务并保持 GUI 运行
    （headless 模式依赖同一 IPC 通道，杀死 GUI 会同时摧毁通道）。

    注意：WithoutUserInterface 模式需要管理员权限（请求的操作需要提升）。
    如果运行 Python 的进程没有管理员权限，headless 模式将不可用。
    在这种情况下应使用 tia_session(mode="gui") 附加到运行中的 Portal 进程。

    Returns:
        True 表示服务已就绪，False 表示无法初始化
    """
    import subprocess, time, sys

    # 1) 先试探 headless 连接
    try:
        import clr
        from config_loader import cfg
        _tia_dir = cfg.tia.install_dir
        _tia_ver = cfg.tia.version
        # V21 使用模块化 DLL（Base + Step7），V18 使用单一 DLL
        if _tia_ver >= "V21":
            clr.AddReference(rf'{_tia_dir}\PublicAPI\{_tia_ver}\net48\Siemens.Engineering.Base.dll')
            clr.AddReference(rf'{_tia_dir}\PublicAPI\{_tia_ver}\net48\Siemens.Engineering.Step7.dll')
        else:
            clr.AddReference(rf'{_tia_dir}\PublicAPI\{_tia_ver}\Siemens.Engineering.dll')
        clr.AddReference(rf'{_tia_dir}\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
        from Siemens.Engineering import TiaPortal, TiaPortalMode

        tia = TiaPortal(TiaPortalMode.WithoutUserInterface)
        tia.Dispose()
        print('   ✅ TIA Portal 服务已就绪')
        return True
    except Exception as e:
        msg = str(e)
        if 'Connection to TiaPortal failed' not in msg and 'OpennessAccessException' not in msg:
            # 不是连接问题，可能是其他错误
            print(f'   ⚠ headless 检查异常（非连接问题）: {msg[:100]}')
            return True  # 让调用方决定

    # 2) 连接失败 → 启动 TIA Portal GUI 初始化服务
    print('   🚀 TIA Portal 服务未初始化，启动 GUI 来初始化...')
    try:
        from config_loader import cfg
        tia_bin = os.path.join(cfg.tia.install_dir, 'Bin', 'Siemens.Automation.Portal.exe')
    except Exception:
        tia_bin = r'D:\TIA BEN TI\Portal V18\Bin\Siemens.Automation.Portal.exe'

    if not os.path.exists(tia_bin):
        print(f'   ❌ 未找到 TIA Portal: {tia_bin}')
        return False

    # 启动 GUI（不带项目参数，只为了初始化服务）
    # TIA Portal 需要管理员权限，非 admin 进程需要用 ShellExecuteW runas 提权
    import ctypes
    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    if is_admin:
        subprocess.Popen([tia_bin], shell=True)
    else:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", tia_bin, "", None, 1
        )
    print(f'   ⏳ 等待 TIA Portal 初始化 (最多 {timeout_sec}s)...')

    deadline = time.time() + timeout_sec
    started = False
    while time.time() < deadline:
        r = subprocess.run(
            ['cmd.exe', '/c', 'tasklist', '/fi', 'IMAGENAME eq Siemens.Automation.Portal.exe', '/fo', 'csv', '/nh'],
            capture_output=True, text=True, encoding='gbk', errors='replace',
        )
        if r.stdout and 'Siemens.Automation.Portal.exe' in r.stdout:
            started = True
            break
        time.sleep(3)

    if not started:
        print('   ⚠ TIA GUI 未能在超时内启动')
        return False

    # 等 TIA 完全加载（包括插件、服务注册）
    print('   ⏳ 等待 TIA Portal 完全加载...')
    time.sleep(20)

    # 3) 验证 headless 连接（GUI 保持打开 — headless 模式依赖同一 IPC 通道）
    print('   ✅ TIA Portal GUI 已启动，后台服务就绪')
    return True


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

    # 加载 TIA Openness DLL（V21 使用模块化 DLL）
    try:
        from config_loader import cfg
        _tia_dir = cfg.tia.install_dir
        _tia_ver = cfg.tia.version
    except Exception:
        _tia_dir = r'D:\TIA BEN TI\Portal V21'
        _tia_ver = 'V21'

    if _tia_ver >= "V21":
        clr.AddReference(rf'{_tia_dir}\PublicAPI\{_tia_ver}\net48\Siemens.Engineering.Base.dll')
        clr.AddReference(rf'{_tia_dir}\PublicAPI\{_tia_ver}\net48\Siemens.Engineering.Step7.dll')
    else:
        clr.AddReference(rf'{_tia_dir}\PublicAPI\{_tia_ver}\Siemens.Engineering.dll')
    clr.AddReference(rf'{_tia_dir}\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode
    from System.IO import FileInfo

    # headless 模式下先确保服务已初始化
    if mode == "headless":
        ensure_service_initialized()

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
