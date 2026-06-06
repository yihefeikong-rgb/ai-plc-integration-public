"""
将 TIA Portal 项目下载到 PLCSIM 仿真 PLC。

下载策略（按优先级）:
  1. C# TiaWorker — 编译过的 C# 可执行文件，直接调用 Openness API
     使用 WithoutUserInterface 模式，无需 TIA Portal GUI
  2. Python API — 通过 Openness DownloadProvider API 下载
     使用 GUI 模式（附加到运行中 Portal）
  3. UI Automation — 模拟 GUI 点击下载（后备）
  4. 手动指引 — 如果以上均不可用

用法:
  python download_to_plcsim.py                        # 默认（自动选择最优方式）
  python download_to_plcsim.py --compile-first        # 下载前先编译
  python download_to_plcsim.py --python               # 强制 Python API 模式
  python download_to_plcsim.py --ui                   # 强制 UI Automation 模式
  python download_to_plcsim.py --tiaworker            # 强制 TiaWorker C# 模式
"""

import sys, os, json, subprocess as _sp, tempfile
from pathlib import Path

from config_loader import cfg
TIA_PROJECT = cfg.tia.project_path


def _ensure_tia_gui_running(timeout_sec: int = 120) -> bool:
    """确保 TIA Portal GUI 正在运行。

    如果不在运行，通过 PortalBA.exe 启动它（支持 UAC 提权）。
    启动后等待 TIA Portal 完全加载完成。

    Returns:
        True 表示 TIA Portal GUI 可用，False 表示启动失败
    """
    import subprocess, time, ctypes

    # 检查是否已在运行（用 cmd.exe 避免 git bash 参数转发问题）
    r = subprocess.run(
        ['cmd.exe', '/c', 'tasklist', '/fi', 'IMAGENAME eq Siemens.Automation.Portal.exe', '/fo', 'csv', '/nh'],
        capture_output=True, text=True, encoding='gbk', errors='replace',
    )
    if r.stdout and 'Siemens.Automation.Portal.exe' in r.stdout:
        print('   ✅ TIA Portal GUI 已在运行')
        return True

    # 启动 TIA Portal GUI
    tia_bin = os.path.join(cfg.tia.install_dir, 'Bin', 'Siemens.Automation.Portal.exe')
    if not os.path.exists(tia_bin):
        print(f'   ⚠ 未找到 TIA Portal: {tia_bin}')
        return False

    print(f'   🚀 启动 TIA Portal GUI (最多等 {timeout_sec}s)...')
    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    if is_admin:
        subprocess.Popen([tia_bin, '/T', cfg.tia.project_path])
    else:
        # TIA Portal 需要管理员权限，用 ShellExecuteW runas 弹出 UAC 提权
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", tia_bin,
            f'"/T" "{cfg.tia.project_path}"',
            None, 1
        )

    # 轮询等待进程出现
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        r = subprocess.run(
            ['cmd.exe', '/c', 'tasklist', '/fi', 'IMAGENAME eq Siemens.Automation.Portal.exe', '/fo', 'csv', '/nh'],
            capture_output=True, text=True, encoding='gbk', errors='replace',
        )
        if r.stdout and 'Siemens.Automation.Portal.exe' in r.stdout:
            print('   ✅ TIA Portal GUI 已启动，等待项目加载...')
            time.sleep(15)  # 给项目加载留时间
            return True
        time.sleep(5)

    print(f'   ⚠ TIA Portal GUI 启动超时')
    return False


def _try_download_via_python(compile_first: bool = False, target_ip: str = "") -> int:
    """通过 Python tia_session + DownloadProvider API 下载。

    流程:
      1. 确保 TIA Portal GUI 正在运行（仅一次）
      2. 单个 GUI 模式会话 — tia_session(mode="gui") 附加到运行中 Portal
      3. 在同一个会话内：先编译（可选），再下载到 PLCSIM
      4. 失败则返回 -1 触发 UI Automation fallback

    注意:
      - 始终使用 GUI 模式而非 headless，因为 WithoutUserInterface 需要管理员权限
      - 编译和下载在同一个 GUI 会话中完成，避免重复 attach/detach
    """
    from tia_session import tia_session

    print('🔌 通过 Python API 下载到 PLCSIM...')

    # V21 需要 PLCSIM GUI 窗口在运行，否则扫描不到设备
    print('   确保 PLCSIM GUI 已启动...')
    try:
        from plcsim_api import _ensure_user_interface
        _ensure_user_interface()
        import time
        time.sleep(3)
    except Exception as e:
        print(f'   ⚠ PLCSIM GUI 启动检查异常（继续）: {e}')

    print()

    # 确保 TIA Portal GUI 运行中（仅启动一次，编译和下载共用同一会话）
    if not _ensure_tia_gui_running():
        print('⚠ 无法启动 TIA Portal GUI，切换至 UI Automation')
        return -1

    # 单个 GUI 会话：先编译（可选），后下载
    print('📥 连接 TIA Portal GUI...')
    try:
        with tia_session(mode="gui") as (project, plc_sw):
            if not plc_sw:
                print('❌ 未找到 PLC 设备')
                return 1

            # ── Step 1: 编译（可选） ──
            if compile_first:
                print('📦 编译中...')
                from Siemens.Engineering.Compiler import ICompilable
                compiler = plc_sw.GetService[ICompilable]()
                cr = compiler.Compile()
                if cr.ErrorCount > 0:
                    print(f'   ❌ 编译失败: Errors={cr.ErrorCount}')
                    return 1
                print(f'   ✅ 编译成功: Warnings={cr.WarningCount}')
                project.Save()
                print()

            # ── Step 2: 下载到 PLCSIM ──
            from Siemens.Engineering.Download import (
                DownloadProvider, DownloadConfigurationDelegate,
                DownloadOptions, DownloadResultState,
            )

            dev = project.Devices[0]

            def find_dp(item, depth=0):
                if depth > 5: return None
                try:
                    dp = item.GetService[DownloadProvider]()
                    if dp: return dp
                except: pass
                for child in item.DeviceItems:
                    r = find_dp(child, depth + 1)
                    if r: return r
                return None

            dp = find_dp(dev)
            if dp is None:
                print('❌ DownloadProvider 不可用')
                return -1

            cc = dp.Configuration
            mode = cc.Modes.Find("PN/IE")
            if mode is None:
                print('❌ 未找到 PN/IE')
                return -1

            pc_iface = None
            for i in mode.PcInterfaces:
                name = str(i.Name).upper()
                if 'PLCSIM' in name:
                    # 优先选纯 "PLCSIM" 接口（Softbus 模式），而非虚拟以太网适配器
                    if 'ETHERNET' not in name and 'VIRTUAL' not in name:
                        pc_iface = i
                        break
                    # 记住第一个候选（可能在列表前面）
                    if pc_iface is None:
                        pc_iface = i
            pc_iface = pc_iface or (mode.PcInterfaces[0] if mode.PcInterfaces.Count > 0 else None)
            if pc_iface is None:
                print('❌ 未找到可用网卡')
                return -1

            target = pc_iface.TargetInterfaces[0] if pc_iface.TargetInterfaces.Count > 0 else None
            if target is None:
                print('❌ 未找到目标 PLC')
                return -1

            ip = target_ip or '10.0.0.1'
            addr = target.Addresses.Create(ip)

            print(f'   网卡: {pc_iface.Name}')
            print(f'   目标: {target.Name} @ {ip}')

            def on_pre(c):
                try:
                    # V21 关键：设置下载目标为 PLCSIM Advanced（而非默认的 CPU）
                    p = c.GetType().GetProperty('TargetForSoftware')
                    if p:
                        target_obj = p.GetValue(c, None)
                        if target_obj:
                            sel_p = target_obj.GetType().GetProperty('CurrentSelection')
                            if sel_p:
                                sel_type = sel_p.PropertyType
                                # 选择 PlcSimulationAdvanced（枚举值）
                                try:
                                    adv = sel_type.GetEnumValues().GetValue(1)  # 1 = PlcSimulationAdvanced
                                    sel_p.SetValue(target_obj, adv, None)
                                except:
                                    pass
                except: pass

            def on_post(c):
                try:
                    p = c.GetType().GetProperty('TargetForSoftware')
                    if p:
                        target_obj = p.GetValue(c, None)
                        if target_obj:
                            sel_p = target_obj.GetType().GetProperty('CurrentSelection')
                            if sel_p:
                                sel_type = sel_p.PropertyType
                                try:
                                    adv = sel_type.GetEnumValues().GetValue(1)
                                    sel_p.SetValue(target_obj, adv, None)
                                except:
                                    pass
                except: pass

            print('📥 正在下载到 PLCSIM...')
            result = dp.Download(
                target, addr,
                DownloadConfigurationDelegate(on_pre),
                DownloadConfigurationDelegate(on_post),
                DownloadOptions.Software,
            )
            success = result.State == DownloadResultState.Success
            print(f'   状态: {result.State}, 错误: {result.ErrorCount}')
            if success:
                print('✅ 下载成功！')
                project.Save()
                return 0
            else:
                print(f'⚠ 下载状态: {result.State}')
                project.Save()
                return 0
    except Exception as e:
        msg = str(e)
        print(f'⚠ 下载异常: {msg[:200]}')
        if 'Connection to TiaPortal failed' in msg:
            print('   TIA Portal GUI 连接失败（可能未完全启动）')
        return -1


def download_via_ui(compile_first: bool = False) -> int:
    from pathlib import Path as _Path

    dl_script = _Path(__file__).parent / 'dl_plcsim_gui.py'
    project_name = os.path.basename(TIA_PROJECT)

    print(f'   启动 UI Automation 下载...')
    timeout_val = 180
    try:
        r = _sp.run(
            [sys.executable, str(dl_script), project_name, '--timeout', str(timeout_val)],
            capture_output=True, text=True, timeout=timeout_val + 30,
            encoding='utf-8', errors='replace',
        )
        result = json.loads(r.stdout.strip()) if r.stdout.strip() else {}
    except _sp.TimeoutExpired:
        print('   ❌ UI Automation 超时')
        return 1
    except json.JSONDecodeError:
        print(f'   ❌ 无法解析 UI 输出: {r.stdout[:200] if r.stdout else "空"}')
        return 1
    except Exception as e:
        print(f'   ❌ UI Automation 异常: {e}')
        return 1

    if result.get('success'):
        print('   ✅ TIA Portal GUI 下载完成')

        # Step 3: 自动更新 golden backup
        print()
        print('📦 更新 golden backup...')
        try:
            from plcsim_api import archive_instance
            project_dir = os.path.dirname(TIA_PROJECT)
            golden_zip = os.path.join(project_dir, 'factory_io1_golden.zip')
            storage_path = os.path.join(project_dir, 'plcsim_storage')
            archive_instance(cfg.factory_io.plcsim_instance, golden_zip, storage_path)
            print(f'   ✅ Golden backup 已更新: {golden_zip}')
        except Exception as e:
            print(f'   ⚠ Golden backup 更新失败（不影响下载）: {e}')

        print()
        print('=' * 60)
        print('🎉 完整闭环完成！')
        print('   编译 ✅ → UI 下载 ✅ → Golden backup ✅')
        print('=' * 60)
        return 0
    else:
        error_msg = result.get('error', '未知错误')
        print(f'   ❌ UI Automation 下载失败: {error_msg}')
        print()
        print('📋 手动下载: 打开 TIA Portal GUI → 右键 PLC_1 → 下载到设备 → 软件')
        return 1


def _try_download_via_tiaworker(compile_first: bool = False, target_ip: str = "") -> int:
    """通过 C# TiaWorker 可执行文件下载到 PLCSIM。

    TiaWorker 使用 WithoutUserInterface 模式直接调用 Openness API，
    无需 TIA Portal GUI 运行中。已使用 V21 DLL 编译。

    Returns:
        0: 成功, 1: 失败, -1: TiaWorker 不可用（触发 fallback）
    """
    tiaworker_exe = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'bin', 'TiaWorker.exe'
    )

    if not os.path.exists(tiaworker_exe):
        print('   ⚠ TiaWorker 未编译，跳过')
        return -1

    print('🔌 通过 C# TiaWorker 下载到 PLCSIM...')

    # 先清理残留的 TIA Portal 进程（避免项目锁定）
    import subprocess as _sp_ui
    print('   清理 TIA Portal 残留进程...')
    _sp_ui.run(['cmd.exe', '/c', 'taskkill', '/f', '/im', 'Siemens.Automation.Portal.exe'],
               capture_output=True, timeout=5)
    _sp_ui.run(['cmd.exe', '/c', 'taskkill', '/f', '/im', 'Siemens.Automation.Portal.exe'],
               capture_output=True, timeout=5)
    import time as _time
    _time.sleep(5)  # 等 5 秒确保锁释放

    # V21 需要 PLCSIM GUI 窗口在运行，否则扫描不到设备
    print('   确保 PLCSIM GUI 已启动...')
    try:
        from plcsim_api import _ensure_user_interface
        _ensure_user_interface()
        _time.sleep(3)  # 给 GUI 窗口留出注册时间
    except Exception as e:
        print(f'   ⚠ PLCSIM GUI 启动检查异常（继续）: {e}')

    # 准备 JSON 输入
    project_path = cfg.tia.project_path
    input_data = {
        "ProjectPath": project_path,
        "InterfaceName": "PN/IE",
        "TargetIp": target_ip or "10.0.0.1",
        "DeviceName": "",
        "TimeoutSec": 120,
    }

    # 写入临时文件
    import tempfile as _tf
    tmp = _tf.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(input_data, tmp)
    tmp_path = tmp.name
    tmp.close()

    try:
        print(f'   启动 TiaWorker (headless)...')
        r = _sp.run(
            [tiaworker_exe, "download", tmp_path],
            capture_output=True, text=True, timeout=180,
            encoding='utf-8', errors='replace',
        )
        stdout = r.stdout.strip()
        stderr = r.stderr.strip()
        if stderr:
            print(f'   [stderr] {stderr[:300]}')

        if stdout:
            result = json.loads(stdout)
            if result.get('status') == 'ok':
                data = result.get('data', {})
                if data.get('success'):
                    print(f'   ✅ TiaWorker 下载成功！')
                    return 0
                elif data.get('note') == 'auto':
                    print(f'   ⚠ TiaWorker: {data.get("message", "需要手动确认")}')
                    print(f'   回退到其他下载方式...')
                    return -1
                else:
                    print(f'   ❌ TiaWorker 下载失败: {data.get("message", "未知错误")}')
                    return 1
            else:
                print(f'   ❌ TiaWorker 返回错误: {result.get("error", "未知")}')
                return 1
        else:
            print('   ⚠ TiaWorker 无输出，回退')
            return -1
    except json.JSONDecodeError as e:
        print(f'   ⚠ TiaWorker 输出解析失败: {e}')
        print(f'   原始输出: {stdout[:200] if stdout else "(空)"}')
        return -1
    except _sp.TimeoutExpired:
        print('   ❌ TiaWorker 超时（180s）')
        return 1
    except Exception as e:
        print(f'   ⚠ TiaWorker 异常: {e}')
        return -1
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _ensure_admin() -> bool:
    """确保以管理员权限运行。如不是，提示用户以管理员身份重新运行。

    TIA Portal Openness API (TiaPortal) 需要管理员权限，无论 headless 还是 GUI 模式。
    如果当前不是管理员，尝试通过 ShellExecuteW runas 自提权（会弹出 UAC 对话框）。
    提权后原进程退出，新进程以管理员身份运行。

    Returns:
        True 表示已具有管理员权限，False 表示提权失败或用户取消
    """
    import ctypes
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True

    print()
    print('╔' + '═' * 58 + '╗')
    print('║ ⚠ TIA Portal Openness API 需要管理员权限                    ║')
    print('║    正在通过 UAC 请求提权...                                 ║')
    print('╚' + '═' * 58 + '╝')
    print()

    # 通过 ShellExecuteW runas 启动新进程（会弹出 UAC 对话框）
    script = os.path.abspath(sys.argv[0])
    args = ' '.join(f'"{a}"' if ' ' in a else a for a in sys.argv[1:])
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}" {args}', None, 1
    )
    # ShellExecuteW 返回值 > 32 表示成功
    if ret <= 32:
        print('⚠ UAC 提权失败或用户取消。')
        print()
        print('请手动以管理员身份运行:')
        print(f'   "D:/Python3/python.exe" {script} {" ".join(sys.argv[1:])}')
        print()
        print('或者以管理员身份打开命令提示符 (Win+X → 终端(管理员))')
        return False
    sys.exit(0)


def main():
    # 检查管理员权限 — TIA Portal Openness API 需要管理员权限
    if not _ensure_admin():
        return 1

    compile_first = '--compile-first' in sys.argv
    force_tiaworker = '--tiaworker' in sys.argv
    force_python = '--python' in sys.argv
    force_ui = '--ui' in sys.argv
    target_ip = ''
    args = sys.argv[1:]

    i = 0
    while i < len(args):
        a = args[i]
        if a == '--ip' and i + 1 < len(args):
            i += 1
            target_ip = args[i]
        elif a in ('--compile-first', '--ui', '--python', '--tiaworker'):
            pass
        elif a.startswith('--'):
            print(f'未知参数: {a}')
            print(__doc__)
            return 1
        i += 1

    if not os.path.exists(TIA_PROJECT):
        print(f'❌ 项目不存在: {TIA_PROJECT}')
        return 1

    print(f'   项目: {os.path.basename(TIA_PROJECT)}')

    # ── 主下载策略 ──
    if force_ui:
        return download_via_ui(compile_first)
    if force_tiaworker:
        return _try_download_via_tiaworker(compile_first, target_ip)
    if force_python:
        rc = _try_download_via_python(compile_first, target_ip)
        if rc == 0:
            return 0
        print(f'\n⚠ Python API 下载失败')
        return 1

    # 默认策略：TiaWorker → Python API → UI Automation → 手动
    print(f'📥 下载策略: TiaWorker(C#) → Python API → UI Automation → 手动指引')
    print()
    rc = _try_download_via_tiaworker(compile_first, target_ip)
    if rc == 0:
        return 0

    if rc == -1:
        print()
        print(f'⚠ TiaWorker 不可用，切换至 Python API...')
        rc = _try_download_via_python(compile_first, target_ip)
        if rc == 0:
            return 0

    if rc == -1:
        print()
        print(f'⚠ Python API 不可用，切换至 UI Automation...')
        rc = download_via_ui(compile_first=False)
        if rc == 0:
            return 0

    print()
    print('=' * 60)
    print('📋 手动下载指引:')
    print()
    print('   1. 打开 TIA Portal')
    print('   2. 打开项目 → 右键 PLC 设备 → 下载到设备')
    print('   3. PG/PC 接口选 PLCSIM / PLCSIM Virtual Ethernet Adapter')
    print('   4. 选择"软件（全部）" → 下载')
    print()
    print('   完成后，验证:')
    print('   - PLCSIM 应处于 RUN 模式')
    print('   - Factory I/O 场景应响应 PLC 程序')
    print('=' * 60)
    return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\n⚠️  用户中断')
        sys.exit(1)
