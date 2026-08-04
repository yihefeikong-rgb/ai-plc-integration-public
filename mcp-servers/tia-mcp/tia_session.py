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
import csv
import subprocess
import sys
import time
import gc
import os
from contextlib import contextmanager
from pathlib import Path


def _current_user() -> str:
    """当前 Windows 用户标识（'DOMAIN\\USERNAME'），获取不到时返回空串。

    用作 tasklist /v 输出中 "User Name" 列的匹配基准（属主判断）。
    """
    user = os.environ.get('USERNAME')
    if not user:
        return ''
    domain = os.environ.get('USERDOMAIN')
    return f'{domain}\\{user}' if domain else user


def _tia_portal_snapshot() -> dict:
    """单次快照查询当前用户拥有的 TIA Portal 进程。

    Returns:
        {pid: window_title}。pid 为进程号，window_title 为原始窗口标题
        （无窗口进程通常为 'N/A'）。查询失败返回 {}——fail-closed：
        宁可漏清理，也不基于过期或不可信数据强杀进程。
    """
    snapshot = {}
    try:
        # 单个 /v 查询同时取得 PID、属主（User Name）和窗口标题，
        # 避免旧实现两次 tasklist（先收集全部 PID、再收集有窗口 PID）
        # 之间窗口状态变化造成的 TOCTOU。
        r = subprocess.run(
            ['cmd.exe', '/c', 'tasklist', '/v', '/fi', 'IMAGENAME eq Siemens.Automation.Portal.exe', '/fo', 'csv', '/nh'],
            capture_output=True, text=True,
            encoding='gbk', errors='replace',
        )
        if not r.stdout:
            return snapshot
        owner = _current_user()
        if not owner:
            return snapshot
        for line in r.stdout.strip().split('\n'):
            line = line.strip()
            if not line or 'Siemens.Automation.Portal.exe' not in line:
                continue
            parts = next(csv.reader([line]), [])
            if len(parts) < 9:
                continue
            # 属主判断：只记录当前用户拥有的进程
            if parts[6].strip().casefold() != owner.casefold():
                continue
            pid = parts[1].strip()
            if pid.isdigit():
                snapshot[pid] = parts[8].strip()
    except Exception:
        pass
    return snapshot


def _kill_tia_processes(kill_pids=None):
    """清理残留的 headless TIA Portal 进程（仅杀当前用户的无窗口 headless 实例）

    注意：不能杀 S7* / Siemens* 等系统进程，会误杀 PLCSIM 和 GUI 实例。
    有窗口的 GUI 实例始终受保护（headless 依赖其 IPC 通道，不能杀）。

    kill_pids: 可选白名单，仅清理该集合内的进程。tia_session 传入本会话
    期间新出现的 PID，避免并发 headless 会话互相误杀；None 时清理所有
    属于当前用户的无窗口 TIA Portal 进程。
    """
    try:
        # 杀进程前重新取单次快照：PID、属主、窗口标题在同一快照中判定，
        # 并对每个 PID 附加 IMAGENAME 过滤，缩小 tasklist→taskkill 的
        # TOCTOU 与 PID 复用风险。
        snapshot = _tia_portal_snapshot()
        if kill_pids is not None:
            snapshot = {pid: title for pid, title in snapshot.items() if pid in kill_pids}
        # 只杀无窗口的 headless 实例；有窗口的 GUI 实例（标题非 N/A）受保护
        to_kill = [pid for pid, title in snapshot.items() if title.casefold() in ('n/a', '')]
        if to_kill:
            cmd = ['taskkill', '/f', '/fi', 'IMAGENAME eq Siemens.Automation.Portal.exe']
            for pid in to_kill:
                cmd += ['/pid', pid]
            subprocess.run(cmd, capture_output=True)
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


# 进程内缓存：headless 服务引导（启动 GUI）只执行一次，
# 避免每次会话连接失败都重复启动 GUI 并轮询 120s + sleep(20)。
_service_init_cached = None  # None=未引导; True=已引导成功; False=引导失败


def ensure_service_initialized(timeout_sec: int = 120) -> bool:
    """确保 TIA Portal 后台服务已初始化，headless 连接可用。

    TIA Portal Openness WithoutUserInterface 模式需要 IPC 通道。
    该通道在第一次 GUI 启动后自动初始化且保持存活。
    若 headless 连接失败，启动 GUI 来初始化服务并保持 GUI 运行
    （headless 模式依赖同一 IPC 通道，杀死 GUI 会同时摧毁通道）。

    注意：本函数不自行创建探测连接——探测由会话自身的 TiaPortal
    连接承担（避免重复连接）。仅在会话 headless 连接因服务通道
    未初始化而失败时调用，且每个进程只引导一次（结果缓存）。

    注意：WithoutUserInterface 模式需要管理员权限（请求的操作需要提升）。
    如果运行 Python 的进程没有管理员权限，headless 模式将不可用。
    在这种情况下应使用 tia_session(mode="gui") 附加到运行中的 Portal 进程。

    Returns:
        True 表示服务已就绪，False 表示无法初始化
    """
    global _service_init_cached
    if _service_init_cached is not None:
        return _service_init_cached

    try:
        from config_loader import TargetConfigurationError, cfg, validate_control_target
        validate_control_target()
    except (AttributeError, TargetConfigurationError) as exc:
        print(f'   ❌ 控制目标配置无效: {exc}')
        _service_init_cached = False
        return False

    # 服务通道未初始化 → 启动 TIA Portal GUI 初始化服务
    print('   🚀 TIA Portal 服务未初始化，启动 GUI 来初始化...')
    try:
        tia_bin = os.path.join(cfg.tia.install_dir, 'Bin', 'Siemens.Automation.Portal.exe')
    except Exception as exc:
        print(f'   ❌ 无法从唯一配置读取 TIA 安装目录: {exc}')
        _service_init_cached = False
        return False

    if not os.path.exists(tia_bin):
        print(f'   ❌ 未找到 TIA Portal: {tia_bin}')
        _service_init_cached = False
        return False

    # 启动 GUI（不带项目参数，只为了初始化服务）
    # TIA Portal 需要管理员权限，非 admin 进程需要用 ShellExecuteW runas 提权
    import ctypes
    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    if is_admin:
        subprocess.Popen([tia_bin])
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
        _service_init_cached = False
        return False

    # 等 TIA 完全加载（包括插件、服务注册）
    print('   ⏳ 等待 TIA Portal 完全加载...')
    time.sleep(20)

    # GUI 保持打开 — headless 模式依赖同一 IPC 通道
    print('   ✅ TIA Portal GUI 已启动，后台服务就绪')
    _service_init_cached = True
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

    try:
        from config_loader import TargetConfigurationError, cfg, validate_control_target
        target = validate_control_target()
        _tia_dir = cfg.tia.install_dir
        _tia_ver = target.tia_version
    except (AttributeError, TargetConfigurationError) as exc:
        raise ValueError(f"控制目标配置无效: {exc}") from exc

    configured_project = str(target.project_path)
    if project_path and os.path.normcase(os.path.normpath(project_path)) != os.path.normcase(os.path.normpath(configured_project)):
        raise ValueError("拒绝非唯一配置中的 TIA 项目路径")
    project_path = configured_project

    # 加载 TIA Openness DLL（V21 使用模块化 DLL）

    if _tia_ver >= "V21":
        clr.AddReference(rf'{_tia_dir}\PublicAPI\{_tia_ver}\net48\Siemens.Engineering.Base.dll')
        clr.AddReference(rf'{_tia_dir}\PublicAPI\{_tia_ver}\net48\Siemens.Engineering.Step7.dll')
    else:
        clr.AddReference(rf'{_tia_dir}\PublicAPI\{_tia_ver}\Siemens.Engineering.dll')
    clr.AddReference(rf'{_tia_dir}\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode
    from System.IO import FileInfo

    tia_mode = TiaPortalMode.WithUserInterface if mode == "gui" else TiaPortalMode.WithoutUserInterface
    # 会话开始前快照：清理时只杀本会话期间新出现的 TIA Portal 进程，
    # 避免 finally 中误杀其他并发 headless 会话的进程。
    baseline = _tia_portal_snapshot() if mode == "headless" else {}
    session_pids = set()
    try:
        tia = TiaPortal(tia_mode)
    except Exception as exc:
        # 非 headless 或非“服务通道未初始化”类故障：直接失败（fail-closed）
        if mode != "headless":
            raise
        msg = str(exc)
        if 'Connection to TiaPortal failed' not in msg and 'OpennessAccessException' not in msg:
            print(f'   ❌ headless 连接异常（非服务通道问题，不启动 GUI）: {msg[:100]}')
            raise
        # 服务通道未初始化 → 启动 GUI 引导一次（进程内缓存），然后重试连接
        print(f'   ⚠ headless 连接失败，尝试初始化 TIA 服务: {msg[:100]}')
        if not ensure_service_initialized():
            raise
        tia = TiaPortal(tia_mode)
    # 连接成功后立即记录本会话创建的进程（缩小并发误杀窗口）
    if mode == "headless":
        session_pids = set(_tia_portal_snapshot()) - set(baseline)
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
    except Exception:
        # 调用方异常：不得把破坏性操作（如删块/删表）持久化（fail-closed）。
        # 跳过 Save 并清理，避免删除已在导入/编译失败后落盘。
        raise
    finally:
        # 仅调用方正常返回时才 Save；Save 失败必须上报，否则改动静默丢失
        save_error = None
        if sys.exc_info()[0] is None:
            try:
                if project:
                    project.Save()
            except Exception as exc:
                save_error = exc
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
            _kill_tia_processes(kill_pids=session_pids)
        if save_error is not None:
            raise RuntimeError(f"TIA 工程保存失败，改动可能未持久化: {save_error}") from save_error
