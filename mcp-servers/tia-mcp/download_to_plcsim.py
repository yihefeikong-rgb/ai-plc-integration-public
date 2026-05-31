"""
将 TIA Portal 项目下载到 PLCSIM 仿真 PLC。

用法:
  python download_to_plcsim.py                    # 打开 TIA Portal，显示下载指引
  python download_to_plcsim.py --compile-first    # 下载前先编译
"""

import sys, os, subprocess

# ─── 配置 ───
TIA_PROJECT = r'D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18'
# ────────────


def _kill_tia():
    """强杀 TIA Portal 相关进程（仅用于无 GUI 模式）"""
    for filter_name in ['S7*', 'Tia*']:
        try:
            r = subprocess.run(
                f'tasklist /fi "IMAGENAME eq {filter_name}" /fo csv /nh',
                shell=True, capture_output=True, text=True, encoding='gbk', errors='replace')
        except Exception:
            continue
        stdout = r.stdout or ''
        for line in stdout.strip().split('\n'):
            if line:
                proc = line.replace('"', '').split(',')[0].strip()
                if proc:
                    subprocess.run(['taskkill', '/f', '/im', proc], capture_output=True)


def download(compile_first: bool = False):
    """打开 TIA Portal → 编译（可选）→ 显示下载指引"""
    import clr
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode
    from Siemens.Engineering.HW.Features import SoftwareContainer
    from Siemens.Engineering.Compiler import ICompilable
    from System.IO import FileInfo

    print('🔌 打开 TIA Portal（GUI 模式）...')
    tia = TiaPortal(TiaPortalMode.WithUserInterface)
    try:
        project = tia.Projects.Open(FileInfo(TIA_PROJECT))
        print(f'   ✅ 项目: {project.Name}')

        # 找 PLC
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
        print(f'   ✅ PLC: {plc_sw.Name}')

        # ── 可选：下载前编译 ──
        if compile_first:
            print('📦 编译中...')
            compiler = plc_sw.GetService[ICompilable]()
            cr = compiler.Compile()
            if cr.State.ToString() != 'Success':
                print(f'   ❌ 编译失败: Errors={cr.ErrorCount}, Warnings={cr.WarningCount}')
                return 1
            print(f'   ✅ 编译成功 (Errors=0)')
            project.Save()
            print(f'   💾 项目已保存')

        # ── 尝试程序化下载 ──
        downloaded = False
        try:
            # TIA Openness V18: DownloadProvider 在 Siemens.Engineering.Download 命名空间
            from Siemens.Engineering.Download import DownloadProvider
            dp = target_device.GetService[DownloadProvider]()
            if dp is not None:
                config = dp.PreConfigure()
                if config is not None:
                    dp.Download(config)
                    downloaded = True
                    print('   ✅ 程序化下载完成！')
        except Exception as e:
            print(f'   ⚠ 程序化下载不可用 ({type(e).__name__})，请手动下载')

        # ── 显示指引 ──
        print()
        print('=' * 60)
        if downloaded:
            print('🎉 项目已下载到 PLCSIM！')
        else:
            print('📋 手动下载步骤（TIA Portal 已打开）:')
            print()
            print(f'   1. 项目树 → 右键 {target_device.Name}')
            print('   2. 下载到设备 → 软件（全部）')
            print('   3. PG/PC 接口类型 → PLCSIM')
            print('   4. 点击「下载」→ 完成后「完成」')
        print()
        print('─── 强制表验证步骤 ───')
        print()
        print('   5. 菜单 在线 → 强制表 → 新建强制表')
        print('   6. 添加地址: %I15.0, %I15.1, %I15.2, %I15.3')
        print('   7. 添加地址: %Q15.0, %Q15.1, %Q15.2')
        print('   8. 强制 %I15.0=1 → 观察 %Q15.0 是否变 1')
        print('   9. 强制 %I15.2=0（急停）→ %Q15.0 应变 0')
        print('=' * 60)

        if downloaded:
            return 0
        else:
            print()
            print('⚠ TIA Portal 保持打开，请在 GUI 中完成下载')
            return 0

    except Exception as e:
        print(f'❌ 错误: {e}')
        import traceback
        traceback.print_exc()
        return 1
    # GUI 模式下不 Dispose / 不杀进程，留给用户操作


def main():
    compile_first = False

    for a in sys.argv[1:]:
        if a == '--compile-first':
            compile_first = True
        else:
            print(f'未知参数: {a}')
            print(__doc__)
            return 1

    if not os.path.exists(TIA_PROJECT):
        print(f'❌ 项目不存在: {TIA_PROJECT}')
        return 1

    return download(compile_first)


if __name__ == '__main__':
    sys.exit(main())
