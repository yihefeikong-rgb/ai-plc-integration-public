"""
Factory I/O → TIA Portal 映射生成器

正确方向：Factory I/O 场景决定 IO → 生成 PLC 标签 + OB1 接线代码
不是反过来！

用法:
    python fio_mapper.py                     # 交互模式
    python fio_mapper.py --offset 10         # 指定偏移量
    python fio_mapper.py --scene-file 场景IO.txt  # 从文件读取

工作流:
    1. 在 Factory I/O 打开驱动窗口（F4）
    2. 查看传感器和执行器列表（注意顺序！）
    3. 运行此脚本，输入列表
    4. 生成 → TIA Portal 标签表 + OB1 SCL 代码
"""
import sys
import os
from config_loader import cfg

OUTPUT_DIR = cfg.tia.output_dir
PLC_IP = cfg.simulation.advanced.plc_ip
RACK = cfg.simulation.advanced.rack
SLOT = cfg.simulation.advanced.slot


def read_io_list_interactive():
    """交互式读取传感器/执行器列表"""
    print("=" * 60)
    print("Factory I/O → TIA Portal 映射生成器")
    print("=" * 60)
    print()
    print("先在 Factory I/O 驱动窗口确认列表，按顺序输入。")
    print("提示：Factory I/O 按从左到右、从上到下的顺序排列 IO 点。")
    print()

    sensors = []
    print("─── 传感器列表 (→ PLC %I 地址) ───")
    print("输入传感器名（按顺序），空行结束：")
    i = 0
    while True:
        name = input(f"  传感器[{i}] 名称: ").strip()
        if not name:
            break
        sensors.append(name)
        i += 1
    print(f"  ✓ 共 {len(sensors)} 个传感器")

    print()
    actuators = []
    print("─── 执行器列表 (← PLC %Q 地址) ───")
    print("输入执行器名（按顺序），空行结束：")
    i = 0
    while True:
        name = input(f"  执行器[{i}] 名称: ").strip()
        if not name:
            break
        actuators.append(name)
        i += 1
    print(f"  ✓ 共 {len(actuators)} 个执行器")

    return sensors, actuators


def read_io_list_from_file(filepath):
    """从文本文件读取 IO 列表

    格式:
        [SENSORS]
        At Entry
        At Exit
        BoxS
        [ACTUATORS]
        Conveyor Entry
        Conveyor Left
    """
    sensors = []
    actuators = []
    current = None

    with open(filepath, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.upper().startswith('[SENSOR'):
                current = 'sensors'
            elif line.upper().startswith('[ACTUATOR'):
                current = 'actuators'
            elif current == 'sensors':
                sensors.append(line)
            elif current == 'actuators':
                actuators.append(line)

    return sensors, actuators


def make_tag_name(io_type: str, index: int, name: str) -> str:
    """生成合法的 TIA Portal 标签名

    规则: 字母开头，仅允许字母数字下划线
    """
    # 简化英文名
    clean = name.replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
    # 去除连续下划线
    while '__' in clean:
        clean = clean.replace('__', '_')
    return f"FIO_{io_type}_{clean}"


def make_address(io_type: str, offset: int, index: int) -> str:
    """生成 Siemens 绝对地址

    %I{offset + index//8}.{index % 8}
    %Q{offset + index//8}.{index % 8}
    """
    byte = offset + index // 8
    bit = index % 8
    prefix = '%I' if io_type == 'Input' else '%Q'
    return f"{prefix}{byte}.{bit}"


def generate_tag_table(sensors, actuators, offset_input, offset_output):
    """生成 TIA Portal 标签表"""
    lines = []
    lines.append("Name,Tag Table,Data Type,Address,Comment")
    lines.append("")

    for i, name in enumerate(sensors):
        tag = make_tag_name('I', i, name)
        addr = make_address('Input', offset_input, i)
        lines.append(f'{tag},"Factory IO Tags",Bool,{addr},"FIO Sensor: {name}"')

    for i, name in enumerate(actuators):
        tag = make_tag_name('Q', i, name)
        addr = make_address('Output', offset_output, i)
        lines.append(f'{tag},"Factory IO Tags",Bool,{addr},"FIO Actuator: {name}"')

    return '\n'.join(lines)


def generate_ob1_scl(sensors, actuators, offset_input, offset_output, block_name="FIO_Control"):
    """生成 OB1 SCL 代码（含传感器读取、执行器写入框架）"""
    lines = []
    lines.append(f'// ============================================================')
    lines.append(f'// OB1 — Factory I/O 主循环')
    lines.append(f'// 生成时间: 自动生成')
    lines.append(f'// ============================================================')
    lines.append(f'')
    lines.append(f'// ── 静态变量（保持状态）──')
    lines.append(f'VAR')
    lines.append(f'    // 传感器镜像（从 %I 读取）')
    for i, name in enumerate(sensors):
        tag = make_tag_name('I', i, name)
        lines.append(f'    {tag}_mem : Bool;  // {name}')
    lines.append(f'    // 执行器输出（写入 %Q）')
    for i, name in enumerate(actuators):
        tag = make_tag_name('Q', i, name)
        lines.append(f'    {tag}_out : Bool;  // {name}')
    lines.append(f'END_VAR')
    lines.append(f'')

    lines.append(f'// ── 1. 读取传感器 ──')
    for i, name in enumerate(sensors):
        tag = make_tag_name('I', i, name)
        addr = make_address('Input', offset_input, i)
        lines.append(f'{tag}_mem := "{tag}";  // {addr} {name}')

    lines.append(f'')
    lines.append(f'// ── 2. 控制逻辑（在此编写！）──')
    lines.append(f'// 示例:')
    lines.append(f'// IF {sensors[0].replace(" ", "_")}_mem THEN')
    for a in actuators[:2]:
        a_clean = make_tag_name('Q', actuators.index(a), a)
        lines.append(f'//     {a_clean}_out := TRUE;')
    lines.append(f'// END_IF;')
    lines.append(f'')

    lines.append(f'// ── 3. 写入执行器 ──')
    for i, name in enumerate(actuators):
        tag = make_tag_name('Q', i, name)
        addr = make_address('Output', offset_output, i)
        lines.append(f'"{tag}" := {tag}_out;  // {addr} {name}')
    lines.append(f'')

    return '\n'.join(lines)


def generate_ob1_lad_tags_xml(sensors, actuators, offset_input, offset_output):
    """生成 TIA Portal 可导入的 PLC Tags XML 片段"""
    import xml.etree.ElementTree as ET
    from xml.dom import minidom
    import datetime

    root = ET.Element('Document')
    root.set('xmlns', 'http://www.siemens.com/automation/Openness/SW/TagTable/v1')

    # TagTable
    tag_table = ET.SubElement(root, 'PLC_TagTable')
    ET.SubElement(tag_table, 'Name').text = 'Factory IO Tags'

    all_tags = []

    for i, name in enumerate(sensors):
        all_tags.append((
            make_tag_name('I', i, name),
            make_address('Input', offset_input, i),
            f'FIO Sensor: {name}'
        ))

    for i, name in enumerate(actuators):
        all_tags.append((
            make_tag_name('Q', i, name),
            make_address('Output', offset_output, i),
            f'FIO Actuator: {name}'
        ))

    for tag_name, addr, comment in all_tags:
        tag = ET.SubElement(tag_table, 'PLC_Tag')
        ET.SubElement(tag, 'Name').text = tag_name
        ET.SubElement(tag, 'LogicalAddress').text = addr
        ET.SubElement(tag, 'DataType').text = 'Bool'
        ET.SubElement(tag, 'Comment').text = comment

    rough = ET.tostring(root, encoding='unicode')
    reparsed = minidom.parseString(rough)
    return reparsed.toprettyxml(indent='  ', encoding='utf-8').decode('utf-8')


def main():
    args = sys.argv[1:]

    # 偏移量
    offset_input = 10   # 推荐从 10 开始，避开物理输入
    offset_output = 10

    for i, arg in enumerate(args):
        if arg == '--offset' and i + 1 < len(args):
            offset_input = int(args[i + 1])
            offset_output = int(args[i + 1])
        elif arg == '--offset-input' and i + 1 < len(args):
            offset_input = int(args[i + 1])
        elif arg == '--offset-output' and i + 1 < len(args):
            offset_output = int(args[i + 1])

    # 读取 IO 列表
    scene_file = None
    for i, arg in enumerate(args):
        if arg == '--scene-file' and i + 1 < len(args):
            scene_file = args[i + 1]

    if scene_file:
        sensors, actuators = read_io_list_from_file(scene_file)
    else:
        sensors, actuators = read_io_list_interactive()

    if not sensors and not actuators:
        print("❌ 未输入任何 IO 点")
        return 1

    print()
    print("=" * 60)
    print("生成结果")
    print("=" * 60)
    print(f"  传感器: {len(sensors)} 个 → %I{offset_input}.0 ~ %I{offset_input + (len(sensors)-1)//8}.{(len(sensors)-1)%8}")
    print(f"  执行器: {len(actuators)} 个 → %Q{offset_output}.0 ~ %Q{offset_output + (len(actuators)-1)//8}.{(len(actuators)-1)%8}")
    print()

    # 生成 XML 标签文件
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    xml_path = os.path.join(OUTPUT_DIR, 'fio_tags.xml')
    xml_content = generate_ob1_lad_tags_xml(sensors, actuators, offset_input, offset_output)
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    print(f"✅ TIA Portal 标签文件: {xml_path}")
    print(f"   在 TIA Portal 中: PLC Tags → Import → 选择此 XML")

    # 生成 CSV 标签表（备选）
    csv_path = os.path.join(OUTPUT_DIR, 'fio_tags.csv')
    csv_content = generate_tag_table(sensors, actuators, offset_input, offset_output)
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write(csv_content)
    print(f"✅ CSV 标签表: {csv_path}")

    # 生成 OB1 骨架
    scl_path = os.path.join(OUTPUT_DIR, 'fio_ob1_skeleton.scl')
    scl_content = generate_ob1_scl(sensors, actuators, offset_input, offset_output)
    with open(scl_path, 'w', encoding='utf-8') as f:
        f.write(scl_content)
    print(f"✅ OB1 骨架: {scl_path}")

    # 生成 Factory I/O 场景 IO 列表模板（方便下次使用）
    scene_io_path = os.path.join(OUTPUT_DIR, 'fio_scene_io.txt')
    with open(scene_io_path, 'w', encoding='utf-8') as f:
        f.write("[SENSORS]\n")
        for s in sensors:
            f.write(f"{s}\n")
        f.write("\n[ACTUATORS]\n")
        for a in actuators:
            f.write(f"{a}\n")
    print(f"✅ 场景 IO 列表: {scene_io_path}")
    print(f"   下次可直接用: python fio_mapper.py --scene-file {scene_io_path}")

    print()
    print("─── 下一步 ───")
    print(f"1. TIA Portal → 导入 {xml_path}")
    print(f"2. 打开 {scl_path}，编写控制逻辑")
    print(f"3. 下载到 PLCSIM Advanced")
    print(f"4. Factory I/O → 驱动配置:")
    print(f"   - 方式A (推荐): Siemens S7-PLCSIM, Model: S7-1500 (PLCSIM Advanced)")
    print(f"   - 方式B: Siemens S7-1200/1500, Host: {PLC_IP}")
    print(f"   - Input offset: {offset_input}, Output offset: {offset_output}")
    print(f"5. 连接 → 运行")

    return 0


if __name__ == '__main__':
    sys.exit(main())
