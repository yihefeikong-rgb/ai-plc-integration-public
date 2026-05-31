"""
验证「AI生成_IO映射表」标签表中每个标签的中文注释是否完整。

用法:
  python verify_tag_comments.py
  python verify_tag_comments.py --table "AI生成_IO映射表"  # 指定表名
  python verify_tag_comments.py --verbose                   # 逐条打印
"""

import sys, os, subprocess

# ─── 配置 ───
TIA_PROJECT = r'D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18'
TABLE_NAME = 'AI生成_IO映射表'
# ────────────


def _kill_tia():
    """强杀 TIA Portal 相关进程"""
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


def verify(table_name: str = TABLE_NAME, verbose: bool = False):
    """验证标签表注释"""
    import clr
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode
    from Siemens.Engineering.HW.Features import SoftwareContainer
    from System.IO import FileInfo

    print(f'🔌 连接 TIA Portal...')
    tia = TiaPortal(TiaPortalMode.WithoutUserInterface)
    try:
        project = tia.Projects.Open(FileInfo(TIA_PROJECT))
        print(f'   ✅ 项目: {project.Name}')

        # 找 PLC
        plc_sw = None
        for device in project.Devices:
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
        print(f'   ✅ PLC: {plc_sw.Name}')

        # 找标签表
        tag_table = None
        for t in plc_sw.TagTableGroup.TagTables:
            if str(t.Name) == table_name:
                tag_table = t
                break

        if tag_table is None:
            print(f'❌ 未找到标签表: {table_name}')
            print(f'   现有表:')
            for t in plc_sw.TagTableGroup.TagTables:
                print(f'   • {t.Name}')
            print()
            print(f'   请先运行: python tools/create_io_tag_table.py')
            return 1

        print(f'   ✅ 标签表: {tag_table.Name}')

        # 遍历所有标签
        tags = list(tag_table.Tags)
        total = len(tags)
        ok = 0
        no_comment = []
        bad_format = []

        for tag in tags:
            name = str(tag.Name)
            addr = ''
            comment = ''

            # 获取地址
            try:
                addr = str(tag.LogicalAddress)
            except:
                pass

            # 获取注释（MultilingualText 结构）
            try:
                comment_obj = tag.Comment
                if comment_obj is not None:
                    for item in comment_obj.Items:
                        try:
                            c = str(item.Text)
                            if c:
                                comment = c
                                break
                        except:
                            pass
            except:
                pass

            if not comment:
                no_comment.append((name, addr))
            elif not comment.startswith('【'):
                bad_format.append((name, addr, comment))
            else:
                ok += 1

            if verbose:
                status = '✅' if comment and comment.startswith('【') else '❌'
                c = comment[:60] if comment else '(无注释)'
                print(f'   {status} {name:40s} {addr:10s}  {c}')

        # ── 汇总报告 ──
        print()
        print('=' * 55)
        print(f'📊 标签表验证报告: {table_name}')
        print(f'   总数: {total}')
        print(f'   ✅ 注释完整: {ok} ({100*ok//total if total else 0}%)')
        print(f'   ❌ 缺少注释: {len(no_comment)}')
        print(f'   ⚠ 格式异常:  {len(bad_format)} (不以【开头)')
        print('=' * 55)

        if no_comment:
            print()
            print('缺少注释的标签:')
            for name, addr in no_comment:
                print(f'   • {name}  ({addr})')

        if bad_format:
            print()
            print('格式异常的标签（不以【模板名】开头）:')
            for name, addr, comment in bad_format:
                print(f'   • {name}  ({addr})  → "{comment[:50]}"')

        if ok == total and total > 0:
            print()
            print('🎉 全部标签注释完整！')
            return 0
        elif total == 0:
            print()
            print('⚠ 标签表为空，请检查 create_io_tag_table.py 的输出')
            return 1
        else:
            return 1

    except Exception as e:
        print(f'❌ 错误: {e}')
        import traceback
        traceback.print_exc()
        return 1
    finally:
        tia.Dispose()
        _kill_tia()
        print()
        print('✅ TIA Portal 已关闭')


def main():
    table_name = TABLE_NAME
    verbose = False

    args = sys.argv[1:]
    while args:
        a = args.pop(0)
        if a == '--table' and args:
            table_name = args.pop(0)
        elif a == '--verbose' or a == '-v':
            verbose = True
        else:
            print(f'未知参数: {a}')
            print(__doc__)
            return 1

    if not os.path.exists(TIA_PROJECT):
        print(f'❌ 项目不存在: {TIA_PROJECT}')
        return 1

    return verify(table_name, verbose)


if __name__ == '__main__':
    sys.exit(main())
