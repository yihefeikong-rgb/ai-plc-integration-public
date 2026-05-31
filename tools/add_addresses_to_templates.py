"""
为 templates/ 下所有 JSON 模板的 inputs/outputs 添加 address 字段。

分配策略：按文件名排序，每个模板分配一个输入字节 (%IB<n>) 和输出字节 (%QB<n>)。
对于超过 8 个变量的模板，自动扩展到下一字节。
"""
import json, os, math

TEMPLATES_DIR = 'mcp-servers/tia-mcp/templates'

def main():
    files = sorted(f for f in os.listdir(TEMPLATES_DIR) if f.endswith('.json'))
    in_byte = 0
    out_byte = 0
    updated = []

    for fname in files:
        path = os.path.join(TEMPLATES_DIR, fname)
        with open(path, encoding='utf-8') as f:
            data = json.load(f)

        interface = data.get('interface', {})
        changed = False

        # Assign input addresses
        inputs = interface.get('inputs', [])
        if inputs:
            in_bits_needed = len(inputs)
            in_bytes_needed = max(1, math.ceil(in_bits_needed / 8))
            for i, v in enumerate(inputs):
                bit_offset = i % 8
                byte_offset = i // 8
                addr_byte = in_byte + byte_offset
                v['address'] = f'%I{addr_byte}.{bit_offset}'
            in_byte += in_bytes_needed
            changed = True

        # Assign output addresses
        outputs = interface.get('outputs', [])
        if outputs:
            out_bits_needed = len(outputs)
            out_bytes_needed = max(1, math.ceil(out_bits_needed / 8))
            for i, v in enumerate(outputs):
                bit_offset = i % 8
                byte_offset = i // 8
                addr_byte = out_byte + byte_offset
                v['address'] = f'%Q{addr_byte}.{bit_offset}'
            out_byte += out_bytes_needed
            changed = True

        if changed:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            nin = len(inputs)
            nout = len(outputs)
            print(f"  ✅ {fname}: I={nin} (→%IB{in_byte-nin}..), O={nout} (→%QB{out_byte-nout}..)")
            updated.append(fname)

    print(f"\n🎉 已更新 {len(updated)} 个模板")
    print(f"   输入字节范围: %IB0..%IB{in_byte-1}  ({in_byte} 字节)")
    print(f"   输出字节范围: %QB0..%QB{out_byte-1}  ({out_byte} 字节)")

if __name__ == '__main__':
    main()
