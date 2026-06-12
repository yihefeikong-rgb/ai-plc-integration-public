"""
模板地址偏移重映射工具

用途：将 21 个模板的硬编码地址（%I15.0, %Q15.1 等）映射为
     基于 config.yaml 中 io_offset_input/io_offset_output 的动态地址。

工作原理：
  - 每个模板的 I/Q 地址有各自的基准偏移（最小的字节数）
  - 重映射将整个地址块平移，使基准偏移对齐到目标偏移
  - 例如：I base=0 (2层电梯) → I10.x, I base=15 (电机正反转) → I25.x

用法：
    python remap_template_addresses.py                    # 预览所有模板的地址偏移
    python remap_template_addresses.py --remap            # 执行重映射（原位覆盖）
    python remap_template_addresses.py --remap --preview  # 显示每个模板的改动
    python remap_template_addresses.py --offset-i 0 --offset-q 0  # 指定偏移量
"""

import json, re, sys
from pathlib import Path

# 从 config.yaml 读取偏移（如果 config_loader 可用）
try:
    from config_loader import cfg
    DEFAULT_OFFSET_I = cfg.factory_io.io_offset_input   # 默认 10
    DEFAULT_OFFSET_Q = cfg.factory_io.io_offset_output  # 默认 10
except Exception:
    DEFAULT_OFFSET_I = 10
    DEFAULT_OFFSET_Q = 10

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _parse_address(addr: str) -> tuple[str, int, int] | None:
    """解析 %I15.0 → ('I', 15, 0), %Q10.2 → ('Q', 10, 2)。返回 None 如果格式不匹配"""
    m = re.match(r'^%([IQ])(\d+)\.(\d+)$', addr)
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3))


def _find_base_offset(template_path: Path) -> tuple[int, int]:
    """从模板中所有地址推导出基准偏移（最小的 I 字节数和 Q 字节数）"""
    min_i = 999
    min_q = 999
    with open(template_path, encoding="utf-8") as f:
        data = json.load(f)
    for io_type, key in [("I", "inputs"), ("Q", "outputs")]:
        for var in data.get("interface", {}).get(key, []):
            addr = var.get("address", "")
            parsed = _parse_address(addr)
            if parsed and parsed[0] == io_type:
                byte_offset = parsed[1]
                if io_type == "I":
                    min_i = min(min_i, byte_offset)
                else:
                    min_q = min(min_q, byte_offset)
    return (0 if min_i == 999 else min_i, 0 if min_q == 999 else min_q)


def remap_template(template_path: Path, offset_i: int, offset_q: int, dry_run: bool = True) -> dict:
    """重映射单个模板的地址偏移，返回改动统计"""
    with open(template_path, encoding="utf-8") as f:
        data = json.load(f)

    base_i, base_q = _find_base_offset(template_path)
    changes = []

    for io_type, key, base, target_offset in [
        ("I", "inputs", base_i, offset_i),
        ("Q", "outputs", base_q, offset_q),
    ]:
        for var in data.get("interface", {}).get(key, []):
            addr = var.get("address", "")
            parsed = _parse_address(addr)
            if parsed and parsed[0] == io_type:
                old_byte = parsed[1]
                bit = parsed[2]
                new_byte = target_offset + (old_byte - base)
                new_addr = f"%{io_type}{new_byte}.{bit}"
                if addr != new_addr:
                    changes.append({"variable": var["name"], "old": addr, "new": new_addr})
                    if not dry_run:
                        var["address"] = new_addr

    if not dry_run:
        with open(template_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return {
        "file": template_path.name,
        "blockName": data.get("blockName", "?"),
        "changes": changes,
        "base_i": base_i,
        "base_q": base_q,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="模板地址偏移重映射")
    parser.add_argument("--remap", action="store_true", help="执行重映射（默认只预览）")
    parser.add_argument("--preview", action="store_true", help="显示详细改动")
    parser.add_argument("--offset-i", type=int, default=DEFAULT_OFFSET_I, help=f"输入偏移（默认 {DEFAULT_OFFSET_I}）")
    parser.add_argument("--offset-q", type=int, default=DEFAULT_OFFSET_Q, help=f"输出偏移（默认 {DEFAULT_OFFSET_Q}）")
    args = parser.parse_args()

    templates = sorted(TEMPLATES_DIR.glob("*.json"))
    if not templates:
        print(f"❌ 未找到模板: {TEMPLATES_DIR}")
        return 1

    total_changes = 0
    for tp in templates:
        result = remap_template(tp, args.offset_i, args.offset_q, dry_run=not args.remap)
        n = len(result["changes"])
        total_changes += n
        status = f"⚠ {n} 处改动" if n > 0 else "✓ 无需改动"
        print(f"  {result['file']:20s} base_I={result['base_i']} base_Q={result['base_q']}  {status}")
        if args.preview and result["changes"]:
            for c in result["changes"]:
                print(f"      {c['variable']:15s} {c['old']} → {c['new']}")

    print(f"\n总计: {len(templates)} 个模板, {total_changes} 处地址改动")
    if not args.remap:
        print("提示: 加 --remap 执行重映射")
    return 0


if __name__ == "__main__":
    sys.exit(main())
