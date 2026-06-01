"""
将 TIA Portal 项目下载到 PLCSIM 仿真 PLC。

支持两种模式:
  - V18 免费版: GUI 模式 + 手动下载（PLCSIM 内嵌，无独立 IP）
  - Advanced: PLCSIM Advanced V5.0（虚拟网卡，Factory I/O 可直连）

用法:
  python download_to_plcsim.py                        # 默认模式（从 config.yaml 读）
  python download_to_plcsim.py --compile-first        # 下载前先编译
  python download_to_plcsim.py --backend advanced     # 强制 Advanced 模式
  python download_to_plcsim.py --backend v18          # 强制 V18 模式
"""

import sys, os, subprocess

from config_loader import cfg
TIA_PROJECT = cfg.tia.project_path


def download_v18(compile_first: bool = False):
    """V18 免费版：GUI 模式 + 手动下载指引"""
    from tia_session import tia_session
    from Siemens.Engineering.Compiler import ICompilable

    print('🔌 打开 TIA Portal（GUI 模式，PLCSIM V18）...')
    print()

    # V18 需要 GUI，tia_session 用 headless 不适合下载场景
    # 这里保留原有的手动 GUI 流程
    import clr
    _tia_dir = cfg.tia.install_dir
    clr.AddReference(rf'{_tia_dir}\PublicAPI\V18\Siemens.Engineering.dll')
    clr.AddReference(rf'{_tia_dir}\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode
    from Siemens.Engineering.HW.Features import SoftwareContainer
    from Siemens.Engineering.Compiler import ICompilable as CompSvc
    from Siemens.Engineering.Download import DownloadProvider
    from System.IO import FileInfo

    tia = TiaPortal(TiaPortalMode.WithUserInterface)
    try:
        project = tia.Projects.Open(FileInfo(TIA_PROJECT))
        print(f'   ✅ 项目: {project.Name}')

        plc_sw = None
        target_device = None
        for device in project.Devices:
            target_device = device
            for item in device.DeviceItems:
                try:
                    c = item.GetService[SoftwareContainer]()
                    if c and c.Software and 'PlcSoftware' in c.Software.GetType().FullName:
                        plc_sw = c.Software
                        break
                except:
                    pass
            if plc_sw:
                break

        if not plc_sw:
            print('❌ 未找到 PLC 设备')
            return 1

        print(f'   ✅ 设备: {target_device.Name}')

        if compile_first:
            print('📦 编译中...')
            compiler = plc_sw.GetService[CompSvc]()
            cr = compiler.Compile()
            if cr.State.ToString() != 'Success':
                print(f'   ❌ 编译失败: Errors={cr.ErrorCount}')
                return 1
            print(f'   ✅ 编译成功')
            project.Save()

        # 尝试程序化下载
        downloaded = False
        try:
            dp = target_device.GetService[DownloadProvider]()
            if dp is not None:
                config = dp.PreConfigure()
                if config is not None:
                    dp.Download(config)
                    downloaded = True
                    print('   ✅ 已下载到 PLCSIM V18')
        except Exception as e:
            print(f'   ⚠ 自动下载不可用 ({type(e).__name__})')

        print()
        print('=' * 60)
        if downloaded:
            print('🎉 已下载到 PLCSIM V18！')
        else:
            print('📋 手动下载步骤（TIA Portal 已打开）:')
            print()
            print(f'   1. 项目树 → 右键 {target_device.Name}')
            print('   2. 下载到设备 → 软件（全部）')
            print('   3. PG/PC 接口 → PLCSIM')
            print('   4. 下载 → 完成')
        print()
        print('─── 强制表验证 ───')
        print('   新建强制表 → %I15.0=1 → 观察 %Q15.0')
        print('=' * 60)

        return 0
    finally:
        # GUI 模式不 Dispose，留给用户操作
        pass


def download_advanced(compile_first: bool = False):
    """PLCSIM Advanced V5.0：虚拟网卡 → 自动下载"""
    from tia_session import tia_session
    from Siemens.Engineering.Compiler import ICompilable
    from Siemens.Engineering.Download import DownloadProvider

    adv = cfg.simulation.advanced
    plc_ip = adv.plc_ip
    rack = adv.rack
    slot = adv.slot

    print(f'🔌 PLCSIM Advanced @ {plc_ip} (Rack={rack}, Slot={slot})')
    print()

    # 先检查 Advanced 是否在运行
    print('   检查 PLCSIM Advanced 状态...')
    try:
        r = subprocess.run(['ping', plc_ip, '-n', '1', '-w', '1000'],
                          capture_output=True, text=True)
        if r.returncode != 0:
            print(f'   ⚠ {plc_ip} 无法 ping 通！')
            print(f'   请先启动 PLCSIM Advanced:')
            print(f'   python plcsim_advanced.py start')
            print(f'   → Start Virtual SIMATIC PLC → IP={plc_ip}')
            print(f'   → 或手动: {cfg.simulation.advanced_install_dir}')
            return 1
        print(f'   ✅ {plc_ip} 可达')
    except Exception:
        pass

    # 打开 TIA Portal + 编译 + 下载
    with tia_session(TIA_PROJECT) as (project, plc_sw):
        print(f'   ✅ 项目: {project.Name}')

        if not plc_sw:
            print('❌ 未找到 PLC 设备')
            return 1

        if compile_first:
            print('📦 编译中...')
            compiler = plc_sw.GetService[ICompilable]()
            cr = compiler.Compile()
            if cr.State.ToString() != 'Success':
                print(f'   ❌ 编译失败: Errors={cr.ErrorCount}')
                return 1
            print(f'   ✅ 编译成功')

        # 找目标设备
        target_device = project.Devices[0]

        # 尝试程序化下载
        downloaded = False
        try:
            dp = target_device.GetService[DownloadProvider]()
            if dp is not None:
                config = dp.PreConfigure()
                if config is not None:
                    dp.Download(config)
                    downloaded = True
        except Exception as e:
            print(f'   ⚠ 自动下载失败: {type(e).__name__}')

        print()
        print('=' * 60)
        if downloaded:
            print(f'🎉 已下载到 PLCSIM Advanced @ {plc_ip}！')
        else:
            print(f'📋 手动下载: 设备 → 下载 → PLCSIM Virtual Ethernet Adapter')
            print(f'   目标: {plc_ip}, Rack={rack}, Slot={slot}')
        print()
        print('─── Factory I/O 连接参数 ───')
        print(f'   Driver: Siemens S7-1500')
        print(f'   IP:     {plc_ip}')
        print(f'   Rack:   {rack}')
        print(f'   Slot:   {slot}')
        print(f'   Port:   {adv.port}')
        print()
        print(f'   CSV 映射: {cfg.factory_io.csv_output}')
        print('=' * 60)
        return 0


def main():
    compile_first = '--compile-first' in sys.argv

    backend = cfg.simulation.backend
    for a in sys.argv[1:]:
        if a == '--backend' and sys.argv.index(a) + 1 < len(sys.argv):
            next_idx = sys.argv.index(a) + 1
            backend = sys.argv[next_idx]
        elif a in ('--compile-first',):
            continue
        elif a in ('--backend',):
            continue
        elif a in ('v18', 'advanced'):
            # positional override
            backend = a
        elif a.startswith('--'):
            print(f'未知参数: {a}')
            print(__doc__)
            return 1

    if not os.path.exists(TIA_PROJECT):
        print(f'❌ 项目不存在: {TIA_PROJECT}')
        return 1

    if backend == 'advanced':
        return download_advanced(compile_first)
    else:
        return download_v18(compile_first)


if __name__ == '__main__':
    sys.exit(main())
