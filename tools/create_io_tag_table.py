"""
在 TIA Portal demo 项目中创建 IO 映射标签表（PLC 变量表）。
直接生成 XML 含中文注释 → Import 到 TIA Portal。
"""
import sys, os, ctypes, datetime
from xml.sax.saxutils import escape as xml_escape

if not ctypes.windll.shell32.IsUserAnAdmin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 1)
    sys.exit(0)

TEMPLATES_DIR = r'mcp-servers/tia-mcp/templates'
TIA_PROJECT = r'D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18'
TABLE_NAME = 'AI生成_IO映射表'


def collect_all_tags():
    """从所有模板收集 I/O 标签"""
    import json
    tags = []
    files = sorted(f for f in os.listdir(TEMPLATES_DIR) if f.endswith('.json'))

    for fname in files:
        path = os.path.join(TEMPLATES_DIR, fname)
        with open(path, encoding='utf-8') as f:
            spec = json.load(f)

        template_name = fname.replace('.json', '')
        block_name = spec.get('blockName', template_name)
        iface = spec.get('interface', {})

        for v in iface.get('inputs', []):
            addr = v.get('address', '')
            if not addr:
                continue
            tags.append({
                'name': f'{block_name}_{v["name"]}',
                'type': v.get('type', 'Bool'),
                'address': addr,
                'comment': f'【{template_name}】{v.get("comment", "")}',
            })

        for v in iface.get('outputs', []):
            addr = v.get('address', '')
            if not addr:
                continue
            tags.append({
                'name': f'{block_name}_{v["name"]}',
                'type': v.get('type', 'Bool'),
                'address': addr,
                'comment': f'【{template_name}】{v.get("comment", "")}',
            })

    return tags


def generate_tag_xml(tags, table_name):
    """生成 TIA Portal 标签表 XML（含中文注释）"""
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.0000000Z')
    lines = []
    lines.append('<?xml version="1.0" encoding="utf-8"?>')
    lines.append('<Document>')
    lines.append('  <Engineering version="V18" />')
    lines.append('  <DocumentInfo>')
    lines.append(f'    <Created>{now}</Created>')
    lines.append('    <ExportSetting>None</ExportSetting>')
    lines.append('  </DocumentInfo>')

    # 表
    lines.append(f'  <SW.Tags.PlcTagTable ID="0">')
    lines.append('    <AttributeList>')
    lines.append(f'      <Name>{xml_escape(table_name)}</Name>')
    lines.append('    </AttributeList>')
    lines.append('    <ObjectList>')

    # 每条标签（ID 用大间隔避免冲突）
    for i, tag in enumerate(tags, start=1):
        tag_id = i * 10
        lines.append(f'      <SW.Tags.PlcTag ID="{tag_id}" CompositionName="Tags">')
        lines.append('        <AttributeList>')
        lines.append(f'          <DataTypeName>{tag["type"]}</DataTypeName>')
        lines.append(f'          <LogicalAddress>{xml_escape(tag["address"])}</LogicalAddress>')
        lines.append(f'          <Name>{xml_escape(tag["name"])}</Name>')
        lines.append('        </AttributeList>')
        # 注释（MultilingualText 格式）
        if tag.get('comment'):
            comment_text = xml_escape(tag['comment'])
            comment_id = tag_id + 1
            item_id = tag_id + 2
            lines.append('        <ObjectList>')
            lines.append(f'          <MultilingualText ID="{comment_id}" CompositionName="Comment">')
            lines.append('            <ObjectList>')
            lines.append(f'              <MultilingualTextItem ID="{item_id}" CompositionName="Items">')
            lines.append('                <AttributeList>')
            lines.append('                  <Culture>zh-CN</Culture>')
            lines.append(f'                  <Text>{comment_text}</Text>')
            lines.append('                </AttributeList>')
            lines.append('              </MultilingualTextItem>')
            lines.append('            </ObjectList>')
            lines.append('          </MultilingualText>')
            lines.append('        </ObjectList>')
        lines.append('      </SW.Tags.PlcTag>')

    lines.append('    </ObjectList>')
    lines.append('  </SW.Tags.PlcTagTable>')
    lines.append('</Document>')
    return '\n'.join(lines)


def main():
    print('📋 收集所有模板的 I/O 标签...')
    tags = collect_all_tags()
    print(f'   共 {len(tags)} 个标签')
    print()

    # 生成 XML
    xml = generate_tag_xml(tags, TABLE_NAME)
    xml_path = rf'D:\TIA FANG ZHEN\{TABLE_NAME}.xml'
    os.makedirs(os.path.dirname(xml_path), exist_ok=True)
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(xml)
    print(f'✅ XML 生成: {xml_path} ({len(xml)} chars)')

    # 连接到 TIA Portal
    print('\n🔌 连接到 TIA Portal...')

    import clr
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode
    from Siemens.Engineering.HW.Features import SoftwareContainer
    from System.IO import FileInfo

    tia = TiaPortal(TiaPortalMode.WithUserInterface)
    try:
        project = tia.Projects.Open(FileInfo(TIA_PROJECT))
        print(f'   ✅ 项目: {project.Name}')

        plc_sw = None
        for device in project.Devices:
            for item in device.DeviceItems:
                try:
                    c = item.GetService[SoftwareContainer]()
                    if c and c.Software and 'PlcSoftware' in c.Software.GetType().FullName:
                        plc_sw = c.Software; break
                except: pass
            if plc_sw: break

        if not plc_sw:
            print('❌ 未找到 PLC 设备'); return 1
        print(f'   ✅ PLC: {plc_sw.Name}')

        tag_table_group = plc_sw.TagTableGroup

        # 删除旧表（如果有）
        existing = None
        for t in list(tag_table_group.TagTables):
            if str(t.Name) == TABLE_NAME:
                existing = t
                break
        if existing is not None:
            # 通过 SystemGroup 的 Groups 能力来删除
            # 或者覆盖导入
            print(f'   ⚠ 已存在同名表，将被覆盖')

        # Import 标签表 XML（覆盖模式）
        from Siemens.Engineering import ImportOptions
        imported = tag_table_group.TagTables.Import(
            FileInfo(xml_path),
            getattr(ImportOptions, 'Override')
        )
        count = len(list(imported))
        print(f'   ✅ 导入成功: {count} 个标签')

        # 验证标签数
        for t in tag_table_group.TagTables:
            if str(t.Name) == TABLE_NAME:
                tag_count = len(list(t.Tags))
                print(f'   ✅ 表中标签数: {tag_count}')
                break

        project.Save()
        print(f'   ✅ 项目已保存')

        print()
        print('=' * 55)
        print(f'🎉 IO 映射表创建完成！')
        print(f'   表名: {TABLE_NAME}')
        print(f'   标签数: {len(tags)}')
        print(f'   在 TIA Portal 项目树 → PLC 变量 → {TABLE_NAME} 中查看')
        print('=' * 55)

    except Exception as e:
        print(f'❌ 错误: {e}')
        import traceback; traceback.print_exc()
        return 1
    finally:
        tia.Dispose()
        # 确保 TIA Portal 进程真正结束
        import subprocess
        for filt in ['S7*', 'Tia*']:
            try:
                r = subprocess.run(f'tasklist /fi "IMAGENAME eq {filt}" /fo csv /nh', shell=True, capture_output=True, text=True, encoding='gbk', errors='replace')
            except Exception:
                continue
            stdout = r.stdout or ''
            for line in stdout.strip().split('\n'):
                if line:
                    parts = line.replace('"','').split(',')
                    if parts:
                        proc_name = parts[0].strip()
                        if proc_name:
                            subprocess.run(['taskkill', '/f', '/im', proc_name], capture_output=True)
                            print(f'   💀 已杀进程: {proc_name}')
        print('✅ TIA Portal 已关闭')

    return 0


if __name__ == '__main__':
    sys.exit(main())
