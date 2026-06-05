"""
将 TIA Portal 项目下载到 PLCSIM 仿真 PLC。

下载策略（按优先级）:
  1. Python API — 通过 Openness API DownloadProvider 直接下载（已验证）
  2. UI Automation — 模拟 GUI 点击下载（后备，需 TIA Portal GUI 打开）
  3. 手动指引 — 如果以上均不可用

用法:
  python download_to_plcsim.py                        # 默认（自动选择最优方式）
  python download_to_plcsim.py --compile-first        # 下载前先编译
  python download_to_plcsim.py --python               # 强制 Python API 模式
  python download_to_plcsim.py --ui                   # 强制 UI Automation 模式
"""

import sys, os, json, subprocess as _sp, tempfile
from pathlib import Path

from config_loader import cfg
TIA_PROJECT = cfg.tia.project_path


def _try_download_via_python(compile_first: bool = False, target_ip: str = "") -> int:
    """通过 Python tia_session + DownloadProvider API 下载。

    headless 模式编译，GUI 模式下载（PLCSIM 网卡需要 GUI 会话）。
    如果 TIA Portal GUI 未运行，返回 -1 触发 UI Automation fallback。
    """
    from tia_session import tia_session

    print('🔌 通过 Python API 下载到 PLCSIM...')
    print()

    # Step 1: headless 编译
    if compile_first:
        print('📦 编译中...')
        with tia_session(mode="headless") as (project, plc_sw):
            if not plc_sw:
                print('❌ 未找到 PLC 设备')
                return 1
            from Siemens.Engineering.Compiler import ICompilable
            compiler = plc_sw.GetService[ICompilable]()
            cr = compiler.Compile()
            if cr.ErrorCount > 0:
                print(f'   ❌ 编译失败: Errors={cr.ErrorCount}')
                return 1
            print(f'   ✅ 编译成功: Warnings={cr.WarningCount}')
            project.Save()
        print()

    # Step 2: GUI 模式下载（PLCSIM 虚拟网卡需要 GUI 会话）
    print('📥 尝试 GUI 模式下载...')
    try:
        with tia_session(mode="gui") as (project, plc_sw):
            if not plc_sw:
                print('❌ 未找到 PLC 设备')
                return 1

            from Siemens.Engineering.Download import DownloadProvider, DownloadConfigurationDelegate, DownloadOptions, DownloadResultState

            dev = project.Devices[0]

            def find_dp(item, depth=0):
                if depth > 5: return None
                try:
                    dp = item.GetService[DownloadProvider]()
                    if dp: return dp
                except: pass
                for child in item.DeviceItems:
                    r = find_dp(child, depth+1)
                    if r: return r
                return None

            dp = find_dp(dev)
            if dp is None:
                print('❌ DownloadProvider 不可用')
                return -1

            # 配置 PLCSIM 连接
            cc = dp.Configuration
            mode = cc.Modes.Find("PN/IE")
            if mode is None:
                print('❌ 未找到 PN/IE')
                return -1

            pc_iface = None
            for i in mode.PcInterfaces:
                if 'PLCSIM' in str(i.Name).upper():
                    pc_iface = i
                    break
            pc_iface = pc_iface or (mode.PcInterfaces[0] if mode.PcInterfaces.Count > 0 else None)
            if pc_iface is None:
                print('❌ 未找到可用网卡')
                return -1

            target = pc_iface.TargetInterfaces[0] if pc_iface.TargetInterfaces.Count > 0 else None
            if target is None:
                print('❌ 未找到目标 PLC')
                return -1

            # 指定 IP
            ip = target_ip or '10.0.0.1'
            addr = target.Addresses.Create(ip)

            print(f'   网卡: {pc_iface.Name}')
            print(f'   目标: {target.Name} @ {ip}')

            def on_pre(c):
                try:
                    p = c.GetType().GetProperty('CurrentSelection')
                    if p:
                        p.SetValue(c, p.PropertyType.GetEnumValues().GetValue(0), None)
                except: pass

            def on_post(c):
                try:
                    p = c.GetType().GetProperty('CurrentSelection')
                    if p:
                        p.SetValue(c, p.PropertyType.GetEnumValues().GetValue(0), None)
                except: pass

            print('📥 正在下载到 PLCSIM...')
            result = dp.Download(
                target, addr,
                DownloadConfigurationDelegate(on_pre),
                DownloadConfigurationDelegate(on_post),
                DownloadOptions.Software
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
            print('   TIA Portal GUI 未运行')
        return -1


def _ensure_tia_gui_running(timeout_sec: int = 120) -> bool:
    """确保 TIA Portal GUI 正在运行。

    如果不在运行，通过 PortalBA.exe 启动它。
    启动后等待 TIA Portal 完全加载完成。

    Returns:
        True 表示 TIA Portal GUI 可用，False 表示启动失败
    """
    import subprocess, time

    # 检查是否已在运行
    r = subprocess.run(
        'tasklist /fi "IMAGENAME eq Siemens.Automation.Portal.exe" /fo csv /nh',
        shell=True, capture_output=True, text=True, encoding='gbk', errors='replace',
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
    subprocess.Popen([tia_bin, '/T', cfg.tia.project_path])

    # 轮询等待进程出现
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        r = subprocess.run(
            'tasklist /fi "IMAGENAME eq Siemens.Automation.Portal.exe" /fo csv /nh',
            shell=True, capture_output=True, text=True, encoding='gbk', errors='replace',
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
      1. headless 编译（可选）
      2. 自动启动 TIA Portal GUI（如未运行）
      3. attach → DownloadProvider API 下载到 PLCSIM
      4. 失败则返回 -1 触发 UI Automation fallback
    """
    from tia_session import tia_session

    print('🔌 通过 Python API 下载到 PLCSIM...')
    print()

    # Step 1: headless 编译
    if compile_first:
        print('📦 编译中...')
        with tia_session(mode="headless") as (project, plc_sw):
            if not plc_sw:
                print('❌ 未找到 PLC 设备')
                return 1
            from Siemens.Engineering.Compiler import ICompilable
            compiler = plc_sw.GetService[ICompilable]()
            cr = compiler.Compile()
            if cr.ErrorCount > 0:
                print(f'   ❌ 编译失败: Errors={cr.ErrorCount}')
                return 1
            print(f'   ✅ 编译成功: Warnings={cr.WarningCount}')
            project.Save()
        print()

    # Step 2: 确保 TIA Portal GUI 运行中
    if not _ensure_tia_gui_running():
        print('⚠ 无法启动 TIA Portal GUI，切换到 UI Automation')
        return -1

    # Step 3: GUI 模式下载（PLCSIM 虚拟网卡需要 GUI 会话）
    print('📥 连接 TIA Portal GUI 并下载...')
    try:
        with tia_session(mode="gui") as (project, plc_sw):
            if not plc_sw:
                print('❌ 未找到 PLC 设备')
                return 1

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
                if 'PLCSIM' in str(i.Name).upper():
                    pc_iface = i
                    break
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
                    p = c.GetType().GetProperty('CurrentSelection')
                    if p:
                        p.SetValue(c, p.PropertyType.GetEnumValues().GetValue(0), None)
                except: pass

            def on_post(c):
                try:
                    p = c.GetType().GetProperty('CurrentSelection')
                    if p:
                        p.SetValue(c, p.PropertyType.GetEnumValues().GetValue(0), None)
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


def main():
    compile_first = '--compile-first' in sys.argv
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
        elif a in ('--compile-first', '--ui', '--python'):
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
    if force_python:
        rc = _try_download_via_python(compile_first, target_ip)
        if rc == 0:
            return 0
        print(f'\n⚠ Python API 下载失败')
        return 1

    # 默认策略：Python API → UI Automation → 手动
    print(f'📥 下载策略: Python API → UI Automation → 手动指引')
    print()
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
