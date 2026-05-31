"""
生成 IO 映射 SCL FB 源码。
读取模板 JSON（带 address 字段），输出 IO 映射 FUNCTION_BLOCK。

用法: python gen_io_map.py <模板 JSON 路径> [--output <输出 SCL 路径>]

如果未指定输出路径，只打印到 stdout。
"""

import json, sys, os

def generate_io_map(template_path: str) -> str:
    with open(template_path, encoding='utf-8') as f:
        spec = json.load(f)

    block_name = spec.get('blockName', 'AutoGen')
    block_number = spec.get('blockNumber', 100)
    comment = spec.get('description', '')

    # Display name for UI (SCL TITLE 仅限 ASCII，中文放注释)
    template_name = os.path.splitext(os.path.basename(template_path))[0]
    title = f"IO Mapping - {block_name}"

    # Instance variable: use blockName (safe ASCII identifier)
    inst_name = block_name

    inputs = spec.get('interface', {}).get('inputs', [])
    outputs = spec.get('interface', {}).get('outputs', [])

    # Count how many have addresses
    inputs_with_addr = [v for v in inputs if v.get('address')]
    outputs_with_addr = [v for v in outputs if v.get('address')]

    lines = []
    lines.append(f'// Automatically generated IO Mapping for: {template_name}')
    lines.append(f'FUNCTION_BLOCK "IO_Map_{block_name}"')
    lines.append(f'TITLE = {title}')
    lines.append(f'{{ S7_Optimized_Access := \'TRUE\' }}')
    lines.append(f'VERSION : 0.1')
    lines.append('')
    lines.append('VAR')
    lines.append(f'    // 多实例：原 FB 的实例')
    lines.append(f'    {inst_name} : "{block_name}";')
    lines.append('END_VAR')
    lines.append('')
    lines.append('BEGIN')

    # Input mapping — 用标签表符号名，不用硬编码地址
    if inputs_with_addr:
        lines.append('')
        lines.append('    // ── 输入映射：标签符号 → FB 实例变量 ──')
        for v in inputs_with_addr:
            tag_name = f'{block_name}_{v["name"]}'
            comment_str = f'  // {v["comment"]}' if v.get('comment') else ''
            lines.append(f'    {inst_name}.{v["name"]} := "{tag_name}";{comment_str}')
        lines.append('')
    else:
        lines.append('')
        lines.append('    // ── 输入映射（无物理地址，跳过） ──')
        lines.append('')

    # Call the FB
    lines.append('    // ── 调用原 FB（执行逻辑） ──')
    lines.append(f'    {inst_name}();')
    lines.append('')

    # Output mapping — 用标签表符号名
    if outputs_with_addr:
        lines.append('    // ── 输出映射：FB 实例变量 → 标签符号 ──')
        for v in outputs_with_addr:
            tag_name = f'{block_name}_{v["name"]}'
            comment_str = f'  // {v["comment"]}' if v.get('comment') else ''
            lines.append(f'    "{tag_name}" := {inst_name}.{v["name"]};{comment_str}')
        lines.append('')
    else:
        lines.append('    // ── 输出映射（无物理地址，跳过） ──')

    lines.append('END_FUNCTION_BLOCK')
    lines.append('')

    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    template_path = sys.argv[1]
    output_path = None

    for i, arg in enumerate(sys.argv[2:], start=2):
        if arg == '--output' and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]

    scl_code = generate_io_map(template_path)

    if output_path:
        with open(output_path, 'w', encoding='utf-8-sig') as f:
            f.write(scl_code)
        print(f"✅ IO 映射 SCL → {output_path}  ({len(scl_code)} bytes)")
    else:
        print(scl_code)

    return 0


if __name__ == '__main__':
    sys.exit(main())
