"""
从模板生成 LAD 块到 TIA Portal
用法: python gen_from_template.py <模板名>

示例: python gen_from_template.py 电机正反转
      python gen_from_template.py 8位抢答器
      python gen_from_template.py 星三角启动
      python gen_from_template.py 自动门控制
"""

import sys, os, json, re, subprocess

# ─── 配置（如路径不同改这里） ───
TEMPLATES_DIR = r'mcp-servers/tia-mcp/templates'
CARTGEN_DLL = r'mcp-servers/tia-mcp/CartGen/bin/Release/net8.0/CartGen.dll'
TIA_PROJECT = r'D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18'
TIA_XML_DIR = r'D:\TIA FANG ZHEN'
# ──────────────────────────────

def _find_plc(project):
    """从项目中获取 PlcSoftware 对象"""
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
                    subprocess.run(['taskkill', '/f', '/im', proc], capture_output=True)


def _ensure_tag_table(plc_sw, current_block_name=''):
    """确保 AI生成_IO映射表 已导入（标签符号名供 IO 映射 SCL 引用）"""
    import json, os, datetime
    from xml.sax.saxutils import escape as xml_escape
    from Siemens.Engineering import ImportOptions
    from System.IO import FileInfo

    TABLE_NAME = 'AI生成_IO映射表'

    # 检查是否已存在
    for t in plc_sw.TagTableGroup.TagTables:
        if str(t.Name) == TABLE_NAME:
            # 已存在，检查是否有当前 FB 需要的标签
            existing_tags = set()
            for tag in t.Tags:
                existing_tags.add(str(tag.Name))
            # 读取当前模板需要的标签名
            needed_tags = set()
            template_json = os.path.join(TEMPLATES_DIR, f'{current_block_name}.json')
            # Try to find by blockName matching
            for fname in os.listdir(TEMPLATES_DIR):
                if fname.endswith('.json'):
                    with open(os.path.join(TEMPLATES_DIR, fname), encoding='utf-8') as f:
                        spec = json.load(f)
                    if spec.get('blockName') == current_block_name:
                        template_json = os.path.join(TEMPLATES_DIR, fname)
                        iface = spec.get('interface', {})
                        for v in iface.get('inputs', []) + iface.get('outputs', []):
                            if v.get('address'):
                                needed_tags.add(f'{current_block_name}_{v["name"]}')
                        break
            missing = needed_tags - existing_tags
            if not missing:
                return  # 标签已齐全

    # 重新生成并导入全部标签表
    tags = []
    for fname in sorted(os.listdir(TEMPLATES_DIR)):
        if not fname.endswith('.json'):
            continue
        with open(os.path.join(TEMPLATES_DIR, fname), encoding='utf-8') as f:
            spec = json.load(f)
        template_name = fname.replace('.json', '')
        block_name = spec.get('blockName', template_name)
        iface = spec.get('interface', {})
        for v in iface.get('inputs', []) + iface.get('outputs', []):
            addr = v.get('address', '')
            if not addr:
                continue
            tags.append({
                'name': f'{block_name}_{v["name"]}',
                'type': v.get('type', 'Bool'),
                'address': addr,
                'comment': f'【{template_name}】{v.get("comment", "")}',
            })

    # 生成 XML
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.0000000Z')
    xml_lines = ['<?xml version="1.0" encoding="utf-8"?>', '<Document>',
                 '  <Engineering version="V18" />',
                 '  <DocumentInfo>',
                 f'    <Created>{now}</Created>',
                 '    <ExportSetting>None</ExportSetting>',
                 '  </DocumentInfo>',
                 f'  <SW.Tags.PlcTagTable ID="0">',
                 '    <AttributeList>',
                 f'      <Name>{xml_escape(TABLE_NAME)}</Name>',
                 '    </AttributeList>',
                 '    <ObjectList>']
    for i, tag in enumerate(tags):
        tid = (i + 1) * 10
        xml_lines.append(f'      <SW.Tags.PlcTag ID="{tid}" CompositionName="Tags">')
        xml_lines.append('        <AttributeList>')
        xml_lines.append(f'          <DataTypeName>{tag["type"]}</DataTypeName>')
        xml_lines.append(f'          <LogicalAddress>{xml_escape(tag["address"])}</LogicalAddress>')
        xml_lines.append(f'          <Name>{xml_escape(tag["name"])}</Name>')
        xml_lines.append('        </AttributeList>')
        if tag.get('comment'):
            c = xml_escape(tag['comment'])
            xml_lines.append('        <ObjectList>')
            xml_lines.append(f'          <MultilingualText ID="{tid+1}" CompositionName="Comment">')
            xml_lines.append('            <ObjectList>')
            xml_lines.append(f'              <MultilingualTextItem ID="{tid+2}" CompositionName="Items">')
            xml_lines.append('                <AttributeList>')
            xml_lines.append('                  <Culture>zh-CN</Culture>')
            xml_lines.append(f'                  <Text>{c}</Text>')
            xml_lines.append('                </AttributeList>')
            xml_lines.append('              </MultilingualTextItem>')
            xml_lines.append('            </ObjectList>')
            xml_lines.append('          </MultilingualText>')
            xml_lines.append('        </ObjectList>')
        xml_lines.append('      </SW.Tags.PlcTag>')
    xml_lines.append('    </ObjectList>')
    xml_lines.append('  </SW.Tags.PlcTagTable>')
    xml_lines.append('</Document>')
    xml_text = '\n'.join(xml_lines)

    # 写入临时文件
    tag_xml_path = os.path.join(TIA_XML_DIR, f'{TABLE_NAME}.xml')
    with open(tag_xml_path, 'w', encoding='utf-8') as f:
        f.write(xml_text)

    # 导入（Override 覆盖同名表）
    try:
        plc_sw.TagTableGroup.TagTables.Import(
            FileInfo(tag_xml_path),
            getattr(ImportOptions, 'Override'))
        tag_count = 0
        for t in plc_sw.TagTableGroup.TagTables:
            if str(t.Name) == TABLE_NAME:
                tag_count = len(list(t.Tags))
                break
        print(f"   📋 标签表: {tag_count} 个标签（含 {current_block_name}）")
    except Exception as e:
        print(f"   ⚠ 标签表导入失败: {e}（IO 映射可能编译失败）")


def main():
    if len(sys.argv) < 2:
        print("用法: python gen_from_template.py <模板名>")
        print()
        print("可选模板:")
        for f in sorted(os.listdir(TEMPLATES_DIR)):
            if f.endswith('.json'):
                name = f.replace('.json', '')
                print(f"  {name}")
        return 1

    name = sys.argv[1]
    json_path = os.path.join(TEMPLATES_DIR, f"{name}.json")

    if not os.path.exists(json_path):
        print(f"❌ 模板不存在: {json_path}")
        print(f"可用模板:")
        for f in sorted(os.listdir(TEMPLATES_DIR)):
            if f.endswith('.json'):
                print(f"  {f.replace('.json', '')}")
        return 1

    print(f"📋 模板: {name}")

    # 1. 读模板
    with open(json_path, encoding='utf-8') as f:
        spec = json.load(f)
    block_name = spec.get('blockName', name)
    net_count = len(spec.get('networks', []))
    print(f"   块名: {block_name}  ({net_count} 个网络)")

    # 2. CartGen → XML
    os.makedirs(TIA_XML_DIR, exist_ok=True)
    xml_path = os.path.join(TIA_XML_DIR, f"{block_name}.xml")
    r = subprocess.run(['dotnet', 'exec', CARTGEN_DLL, json_path, xml_path],
                       capture_output=True, timeout=60)
    if r.returncode != 0:
        err = r.stderr.decode('utf-8', 'ignore')
        print(f"❌ CartGen 失败: {err[:300]}")
        return 1

    # 3. 清洗 XML
    with open(xml_path, 'r', encoding='utf-8') as f:
        xml = f.read()
    # 移除空 MultilingualTextItem
    xml = re.sub(
        r'<MultilingualTextItem[^>]*>\s*<AttributeList>\s*<Culture>[^<]*</Culture>\s*<Text\s*/>\s*</AttributeList>\s*</MultilingualTextItem>\s*',
        '', xml)
    # 移除不合法的 Return 段（FB 不支持）
    xml = re.sub(
        r'<Section\s+Name="Return"[^>]*>.*?</Section>\s*',
        '', xml, flags=re.DOTALL)
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(xml)
    print(f"   ✅ XML: {xml_path} ({len(xml)} bytes)")

    # 4. SVG 预览
    try:
        sys.path.insert(0, r'mcp-servers/tia-mcp')
        from ladder_renderer import render_svg_preview
        svg = render_svg_preview(spec)
        svg_path = os.path.join(TIA_XML_DIR, f"{block_name}.svg")
        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(svg)
        print(f"   ✅ SVG: {svg_path} ({len(svg)} chars)")
    except Exception:
        pass

    # 5. 导入 TIA Portal（两阶段：先导入 FB，关闭重开后导入 IO 映射）
    print("   导入 TIA Portal...")
    import clr, time
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode, ImportOptions
    from Siemens.Engineering.SW import SWImportOptions
    from Siemens.Engineering.SW.ExternalSources import GenerateBlockOption
    from Siemens.Engineering.HW.Features import SoftwareContainer
    from Siemens.Engineering.Compiler import ICompilable
    from System.IO import FileInfo

    # ══ 阶段 1：导入 LAD FB + 编译 ══
    tia = TiaPortal(TiaPortalMode.WithoutUserInterface)
    try:
        project = tia.Projects.Open(FileInfo(TIA_PROJECT))
        print(f"   项目: {project.Name}")
        plc_sw = _find_plc(project)
        if not plc_sw:
            print("❌ 未找到 PLC 设备"); return 1

        plc_sw.BlockGroup.Blocks.Import(
            FileInfo(xml_path), ImportOptions.Override, SWImportOptions(2))
        print("   ✅ FB 导入成功")

        # ⚠ 编译 FB，确保它被 SCL 编译器识别
        compiler = plc_sw.GetService[ICompilable]()
        cr = compiler.Compile()
        print(f"   📦 预编译: State={cr.State}, Errors={cr.ErrorCount}, Warnings={cr.WarningCount}")
        project.Save()
    finally:
        tia.Dispose()
        _kill_tia()

    # ══ 阶段 2：关闭重开 → 导入 IO 映射 SCL ══
    time.sleep(2)

    # 生成 IO 映射 SCL
    sys.path.insert(0, r'mcp-servers/tia-mcp')
    from gen_io_map import generate_io_map
    io_map_scl = generate_io_map(json_path)
    io_map_name = f"IO_Map_{block_name}"
    scl_dir = os.path.join(TIA_XML_DIR, 'scl')
    os.makedirs(scl_dir, exist_ok=True)
    scl_path = os.path.join(scl_dir, f"{io_map_name}.scl")
    with open(scl_path, 'w', encoding='utf-8-sig') as f:
        f.write(io_map_scl)
    print(f"   ✅ IO 映射 SCL: {scl_path}")

    print(f"   🔄 重新打开项目（使编译器看到新 FB）...")
    tia2 = TiaPortal(TiaPortalMode.WithoutUserInterface)
    try:
        project2 = tia2.Projects.Open(FileInfo(TIA_PROJECT))
        plc_sw2 = _find_plc(project2)
        if not plc_sw2:
            print("❌ 重开后未找到 PLC 设备"); return 1

        # ══ 确保标签表已导入（IO 映射 SCL 引用标签符号名） ══
        _ensure_tag_table(plc_sw2, block_name)

        # 导入 IO 映射 SCL
        ext_group = plc_sw2.ExternalSourceGroup
        if ext_group is not None:
            scl_name = os.path.basename(scl_path)
            for es in list(ext_group.ExternalSources):
                if str(es.Name) == scl_name:
                    es.Delete(); break

            ext_source = ext_group.ExternalSources.CreateFromFile(scl_name, scl_path)
            gen_blocks = ext_source.GenerateBlocksFromSource(getattr(GenerateBlockOption, 'None'))
            print(f"   ✅ IO 映射导入: 生成了 {gen_blocks.Count} 个块")
            for b in gen_blocks:
                try:
                    print(f"      → {b.Name}")
                except:
                    print(f"      → <block>")
        else:
            print("   ⚠ ExternalSourceGroup 不可用，跳过")

        # 编译
        compiler = plc_sw2.GetService[ICompilable]()
        cr = compiler.Compile()
        status = '✅' if cr.State.ToString() == 'Success' else f'⚠ State={cr.State}'
        print(f"   📦 编译: {status}, Errors={cr.ErrorCount}, Warnings={cr.WarningCount}")
        project2.Save()
    finally:
        tia2.Dispose()
        _kill_tia()

    print()
    print("=" * 50)
    print(f"🎉 {block_name} (LAD) + IO 映射 已就绪！")
    print("=" * 50)
    return 0


if __name__ == '__main__':
    sys.exit(main())
