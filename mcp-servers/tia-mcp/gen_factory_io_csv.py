"""
从所有模板 JSON 生成 Factory I/O 的 CSV I/O 映射文件。

Factory I/O CSV 格式（Siemens S7-1500 驱动）:
    TagName,Type,Address,Description
    MotorFwd_iStartFwd,Input,15.0,电机正反转-启动正转
    MotorFwd_oRunFwd,Output,15.0,电机正反转-正转运行

用法:
    python gen_factory_io_csv.py              # 生成全部模板的映射
    python gen_factory_io_csv.py --template 电机正反转  # 单个模板
    python gen_factory_io_csv.py --dry-run   # 只打印不写入
"""
import sys, os, json, csv

from config_loader import cfg

TEMPLATES_DIR = cfg.generation.templates_dir
OUTPUT_PATH = cfg.factory_io.csv_output


def parse_address(addr: str) -> tuple:
    """解析 Siemens 绝对地址为 Factory I/O 格式

    %I15.0 → ('Input', 15, 0)
    %Q10.2 → ('Output', 10, 2)
    %M5.3  → ('Memory', 5, 3)
    """
    if not addr:
        return None

    area = addr[1]  # I, Q, M
    rest = addr[2:]  # 15.0

    area_map = {'I': 'Input', 'Q': 'Output', 'M': 'Memory'}
    io_type = area_map.get(area.upper(), 'Unknown')

    try:
        byte_str, bit_str = rest.split('.')
        byte_num = int(byte_str)
        bit_num = int(bit_str)
    except ValueError:
        return None

    return (io_type, byte_num, bit_num)


def generate_csv(template_filter: str = None) -> list:
    """生成 CSV 行列表

    Args:
        template_filter: 为 None 生成全部，否则只生成指定模板名
    Returns:
        行列表，每行为 (tag_name, io_type, address_short, description)
    """
    rows = []

    for fname in sorted(os.listdir(TEMPLATES_DIR)):
        if not fname.endswith('.json'):
            continue
        name = fname.replace('.json', '')
        if template_filter and name != template_filter:
            continue

        path = os.path.join(TEMPLATES_DIR, fname)
        with open(path, encoding='utf-8') as f:
            spec = json.load(f)

        block_name = spec.get('blockName', name)
        iface = spec.get('interface', {})

        # 输入
        for v in iface.get('inputs', []):
            addr = v.get('address', '')
            if not addr:
                continue
            parsed = parse_address(addr)
            if not parsed:
                continue
            io_type, byte_num, bit_num = parsed
            # Factory I/O 格式: "15.0" 不带 %I/%Q 前缀
            addr_short = f"{byte_num}.{bit_num}"
            desc = f"【{name}】{v.get('comment', v['name'])}"
            rows.append((f"{block_name}_{v['name']}", io_type, addr_short, desc))

        # 输出
        for v in iface.get('outputs', []):
            addr = v.get('address', '')
            if not addr:
                continue
            parsed = parse_address(addr)
            if not parsed:
                continue
            io_type, byte_num, bit_num = parsed
            addr_short = f"{byte_num}.{bit_num}"
            desc = f"【{name}】{v.get('comment', v['name'])}"
            rows.append((f"{block_name}_{v['name']}", io_type, addr_short, desc))

    return rows


def main():
    dry_run = '--dry-run' in sys.argv

    template_filter = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--template' and i + 1 < len(sys.argv):
            template_filter = sys.argv[i + 1]

    rows = generate_csv(template_filter)

    if not rows:
        print(f"❌ 未找到任何 I/O 映射")
        return 1

    # 汇总
    inputs = [r for r in rows if r[1] == 'Input']
    outputs = [r for r in rows if r[1] == 'Output']
    memories = [r for r in rows if r[1] == 'Memory']

    print(f"📋 生成 Factory I/O 映射")
    print(f"   Input:  {len(inputs)} 个")
    print(f"   Output: {len(outputs)} 个")
    if memories:
        print(f"   Memory: {len(memories)} 个")
    print(f"   总计:   {len(rows)} 个")
    print()

    if dry_run:
        print("─── 前 10 行预览 ───")
        print(f"{'TagName':<40} {'Type':<8} {'Addr':<8} Description")
        print("-" * 80)
        for r in rows[:10]:
            print(f"{r[0]:<40} {r[1]:<8} {r[2]:<8} {r[3]}")
        if len(rows) > 10:
            print(f"... 还有 {len(rows) - 10} 行")
        return 0

    # 写入 CSV
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['TagName', 'Type', 'Address', 'Description'])
        writer.writerows(rows)

    print(f"✅ CSV 已写入: {OUTPUT_PATH}")
    print(f"   {len(rows)} 行 × 4 列")

    # 提示
    print()
    print("─── Factory I/O 导入步骤 ───")
    print(f"1. 打开 Factory I/O")
    print(f"2. File → Drivers → Siemens S7-1500")
    print(f"3. IP: {cfg.simulation.advanced.plc_ip}")
    print(f"4. Rack: {cfg.simulation.advanced.rack}")
    print(f"5. Slot: {cfg.simulation.advanced.slot}")
    print(f"6. 使用此 CSV 批量绑定 I/O 点")
    print()
    print("⚠️ 注意: 需要先安装 S7-PLCSIM Advanced V5.0")
    print("         免费版 PLCSIM V18 不支持 Factory I/O 直连")

    return 0


if __name__ == '__main__':
    sys.exit(main())
