"""
在 OB1（Main 组织块）中调用 IO 映射 FB。
方案：创建 MasterIO 聚合 FB（多实例）→ 实例 DB → OB1 调用，单个 SCL 文件一次导入。

用法:
  python call_fb_in_ob1.py IO_Map_MotorForwardReverse
  python call_fb_in_ob1.py IO_Map_MotorForwardReverse IO_Map_StarDeltaStarter
  python call_fb_in_ob1.py --list   # 列出项目中已有的 IO_Map_* FB
  python call_fb_in_ob1.py --all    # 自动发现并调用全部 IO_Map_* FB
"""

import sys, os, datetime, subprocess

# ─── 配置 ───
TIA_PROJECT = r'D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18'
TIA_XML_DIR = r'D:\TIA FANG ZHEN'
# ────────────

def generate_combined_scl(fb_names: list) -> str:
    """生成 MasterIO FB + 实例 DB + OB1 的合并 SCL

    结构:
      1. MasterIO FB — 多实例聚合所有 IO_Map_* FB
      2. MasterIO_DB — 实例数据块
      3. Main OB — 调用 MasterIO_DB
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    comment = '、'.join(n.replace('IO_Map_', '') for n in fb_names)

    # 多实例声明
    instances = []
    instance_calls = []
    for i, fb in enumerate(fb_names):
        # 从 IO_Map_MotorForwardReverse → ioMap_MotorForwardReverse
        inst_name = 'ioMap_' + fb.replace('IO_Map_', '')
        instances.append(f'    {inst_name} : "{fb}";')
        instance_calls.append(f'    {inst_name}();')

    return f'''// ═══════════════════════════════════════════════════════════
// AI 自动生成 — MasterIO + OB1 调用链
// 生成时间: {now}
// 聚合 {len(fb_names)} 个 IO 映射 FB: {comment}
// ═══════════════════════════════════════════════════════════

FUNCTION_BLOCK "MasterIO"
TITLE = Master IO Mapping — {comment}
{{ S7_Optimized_Access := 'TRUE' }}
VERSION : 0.1

VAR
    // ══ 多实例：每个 IO_Map_* FB 一个实例 ══
{chr(10).join(instances)}
END_VAR

BEGIN
    // ══ 按顺序调用所有 IO 映射 FB ══
{chr(10).join(instance_calls)}

END_FUNCTION_BLOCK


DATA_BLOCK "MasterIO_DB"
TITLE = Instance DB for MasterIO
{{ S7_Optimized_Access := 'TRUE' }}
VERSION : 0.1
  MasterIO
BEGIN
    
END_DATA_BLOCK


ORGANIZATION_BLOCK "Main"
TITLE = Main Program Sweep (Cycle) — {comment}
{{ S7_Optimized_Access := 'TRUE' }}
VERSION : 0.1

VAR_TEMP
    // Standard OB1 temp interface
    OB1_EV_CLASS : Byte;
    OB1_SCAN_1 : Byte;
    OB1_PRIORITY : Byte;
    OB1_OB_NUMBR : Byte;
    OB1_RESERVED_1 : Byte;
    OB1_RESERVED_2 : Byte;
    OB1_PREV_CYCLE : Int;
    OB1_MIN_CYCLE : Int;
    OB1_MAX_CYCLE : Int;
END_VAR

BEGIN
    
    // ══ 调用 MasterIO（单实例 → 内部级联所有 IO 映射） ══
    "MasterIO_DB"();
    
END_ORGANIZATION_BLOCK
'''


def list_io_map_fbs() -> list:
    """列出项目中已有的 IO_Map_* FB（需要 TIA Portal 已安装）"""
    import clr
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode
    from Siemens.Engineering.HW.Features import SoftwareContainer
    from System.IO import FileInfo

    tia = TiaPortal(TiaPortalMode.WithoutUserInterface)
    try:
        project = tia.Projects.Open(FileInfo(TIA_PROJECT))
        plc_sw = _get_plc_sw(project)
        if not plc_sw:
            return []

        fb_list = []
        for block in plc_sw.BlockGroup.Blocks:
            name = str(block.Name)
            if name.startswith('IO_Map_'):
                fb_list.append(name)
        return sorted(fb_list)
    finally:
        tia.Dispose()
        _kill_tia()


def _get_plc_sw(project):
    """获取 PLC 软件对象"""
    from Siemens.Engineering.HW.Features import SoftwareContainer
    for device in project.Devices:
        for item in device.DeviceItems:
            try:
                c = item.GetService[SoftwareContainer]()
                if c and c.Software and 'PlcSoftware' in c.Software.GetType().FullName:
                    return c.Software
            except:
                pass
    return None


def _kill_tia():
    """强杀 TIA Portal 相关进程"""
    import subprocess
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


def insert_fb_calls(fb_names: list):
    """创建 MasterIO FB + MasterIO_DB + OB1，级联所有 IO 映射 FB"""
    import clr
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode, ImportOptions
    from Siemens.Engineering.SW import SWImportOptions
    from Siemens.Engineering.SW.ExternalSources import GenerateBlockOption
    from Siemens.Engineering.HW.Features import SoftwareContainer
    from Siemens.Engineering.Compiler import ICompilable
    from System.IO import FileInfo

    print(f'🔌 连接 TIA Portal...')
    tia = TiaPortal(TiaPortalMode.WithoutUserInterface)
    try:
        project = tia.Projects.Open(FileInfo(TIA_PROJECT))
        print(f'   ✅ 项目: {project.Name}')

        plc_sw = _get_plc_sw(project)
        if not plc_sw:
            print('❌ 未找到 PLC 设备')
            return 1

        print(f'   ✅ PLC: {plc_sw.Name}')

        # ── 检查哪些 IO_Map_* FB 实际存在 ──
        existing_fbs = set()
        for block in plc_sw.BlockGroup.Blocks:
            existing_fbs.add(str(block.Name))

        valid_fbs = [n for n in fb_names if n in existing_fbs]
        missing = [n for n in fb_names if n not in existing_fbs]

        if missing:
            print(f'   ⚠ 以下 FB 不在项目中，将被跳过: {", ".join(missing)}')

        if not valid_fbs:
            print('❌ 没有可调用的 IO_Map_* FB')
            print('   请先运行: python gen_from_template.py <模板名>')
            return 1

        print(f'   📋 将聚合: {", ".join(valid_fbs)}')

        # ── 生成合并 SCL（MasterIO + DB + OB1）──
        scl = generate_combined_scl(valid_fbs)
        scl_dir = os.path.join(TIA_XML_DIR, 'scl')
        os.makedirs(scl_dir, exist_ok=True)
        scl_path = os.path.join(scl_dir, 'MasterIO_OB1.scl')
        with open(scl_path, 'w', encoding='utf-8-sig') as f:
            f.write(scl)
        print(f'   ✅ 合并 SCL: {scl_path}  ({len(scl)} chars)')

        # ── 先清理旧外部源，再删块（避免外部源引用失效）──
        ext_group = plc_sw.ExternalSourceGroup
        if ext_group is not None:
            for es in list(ext_group.ExternalSources):
                try:
                    n = str(es.Name)
                except:
                    continue
                if n in ('MasterIO_OB1.scl', 'Main.scl', 'MasterIO.scl'):
                    es.Delete()
                    print(f'   🗑 已删除旧外部源: {n}')

        for old_name in ['MasterIO', 'MasterIO_DB', 'Main']:
            for block in list(plc_sw.BlockGroup.Blocks):
                if str(block.Name) == old_name:
                    block.Delete()
                    print(f'   🗑 已删除旧块: {old_name}')

        # ── 导入合并 SCL ──
        if ext_group is not None:
            ext_source = ext_group.ExternalSources.CreateFromFile(
                os.path.basename(scl_path), scl_path)
            gen_blocks = ext_source.GenerateBlocksFromSource(getattr(GenerateBlockOption, 'None'))
            print(f'   ✅ SCL 导入成功: 生成了 {gen_blocks.Count} 个块')
            for b in gen_blocks:
                try:
                    print(f'      → {b.Name}  ({b.TypeIdentifier})')
                except:
                    print(f'      → <block>')
        else:
            print('   ⚠ ExternalSourceGroup 不可用')
            print(f'   请手动: TIA Portal → 外部源文件 → 添加新文件 → {scl_path}')
            return 1

        # ── 编译 ──
        compiler = plc_sw.GetService[ICompilable]()
        cr = compiler.Compile()
        status = '✅ 成功' if cr.State.ToString() == 'Success' else f'⚠ State={cr.State}'
        print(f'   📦 编译: {status}, Errors={cr.ErrorCount}, Warnings={cr.WarningCount}')
        project.Save()
        print(f'   💾 项目已保存')

        print()
        print('=' * 55)
        print(f'🎉 OB1 调用链已就绪！')
        print()
        print(f'   调用链: OB1 → MasterIO_DB → MasterIO')
        for n in valid_fbs:
            inst = 'ioMap_' + n.replace('IO_Map_', '')
            print(f'                         ├─ {inst} → {n}')
        print()
        print(f'   下一步:')
        print(f'   1. python download_to_plcsim.py')
        print(f'   2. 强制表: %I15.0=1 → %Q15.0 响应')
        print('=' * 55)
        return 0

    except Exception as e:
        print(f'❌ 错误: {e}')
        import traceback
        traceback.print_exc()
        return 1
    finally:
        tia.Dispose()
        _kill_tia()
        print('✅ TIA Portal 已关闭')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    if sys.argv[1] == '--list':
        print('🔍 查找项目中的 IO_Map_* FB...')
        fbs = list_io_map_fbs()
        if fbs:
            print(f'   找到 {len(fbs)} 个:')
            for fb in fbs:
                print(f'   • {fb}')
        else:
            print('   (未找到，项目可能为空)')
        return 0

    if sys.argv[1] == '--all':
        print('🔍 自动发现 IO_Map_* FB...')
        fbs = list_io_map_fbs()
        if not fbs:
            print('❌ 未找到任何 IO_Map_* FB，请先生成')
            return 1
        print(f'   找到 {len(fbs)} 个')
        return insert_fb_calls(fbs)

    # 手动指定 FB 名称
    fb_names = sys.argv[1:]
    return insert_fb_calls(fb_names)


if __name__ == '__main__':
    sys.exit(main())
