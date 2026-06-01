"""
批量生成全部 18 个模板的 IO_Map SCL 文件 + 汇总报告。

用法:
    python gen_all_io_maps.py              # 生成全部
    python gen_all_io_maps.py --dry-run    # 只列出，不生成
    python gen_all_io_maps.py --compile    # 生成 + 导入 TIA + 编译
"""
import sys, os, json, time

from config_loader import cfg
from gen_io_map import generate_io_map

TEMPLATES_DIR = cfg.generation.templates_dir
OUTPUT_DIR = os.path.join(cfg.tia.output_dir, 'scl')


def main():
    dry_run = '--dry-run' in sys.argv
    do_compile = '--compile' in sys.argv

    # 收集模板
    templates = []
    for fname in sorted(os.listdir(TEMPLATES_DIR)):
        if fname.endswith('.json'):
            name = fname.replace('.json', '')
            templates.append((name, os.path.join(TEMPLATES_DIR, fname)))

    total = len(templates)
    print(f"📋 找到 {total} 个模板")
    print()

    if dry_run:
        for name, path in templates:
            with open(path, encoding='utf-8') as f:
                spec = json.load(f)
            block_name = spec.get('blockName', name)
            inputs = len(spec.get('interface', {}).get('inputs', []))
            outputs = len(spec.get('interface', {}).get('outputs', []))
            has_addr = any(v.get('address') for v in spec.get('interface', {}).get('inputs', []) + spec.get('interface', {}).get('outputs', []))
            print(f"  {'✅' if has_addr else '⚠️'} {name} → {block_name}  ({inputs}I/{outputs}O)")
        return 0

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    results = {"ok": [], "no_address": [], "error": []}
    start_time = time.time()

    for i, (name, path) in enumerate(templates, 1):
        status = f"[{i}/{total}]"
        try:
            scl_code = generate_io_map(path)
            with open(path, encoding='utf-8') as f:
                spec = json.load(f)
            block_name = spec.get('blockName', name)
            io_map_name = f"IO_Map_{block_name}"
            scl_path = os.path.join(OUTPUT_DIR, f"{io_map_name}.scl")
            with open(scl_path, 'w', encoding='utf-8-sig') as f:
                f.write(scl_code)

            # 检查是否有物理地址
            iface = spec.get('interface', {})
            has_addr = any(
                v.get('address')
                for v in iface.get('inputs', []) + iface.get('outputs', [])
            )
            if has_addr:
                results["ok"].append((name, block_name, scl_path))
                print(f"  {status} ✅ {name} → {io_map_name}.scl  ({len(scl_code)} chars)")
            else:
                results["no_address"].append((name, block_name))
                print(f"  {status} ⚠️ {name} → 无物理地址，跳过")

        except Exception as e:
            results["error"].append((name, str(e)))
            print(f"  {status} ❌ {name}: {e}")

    elapsed = time.time() - start_time

    # ── 汇总报告 ──
    print()
    print("=" * 55)
    print(f"📊 汇总  ({elapsed:.1f}s)")
    print(f"   ✅ 成功: {len(results['ok'])} 个")
    if results['no_address']:
        print(f"   ⚠️ 无物理地址: {len(results['no_address'])} 个")
        for name, _ in results['no_address']:
            print(f"      - {name}")
    if results['error']:
        print(f"   ❌ 失败: {len(results['error'])} 个")
        for name, err in results['error']:
            print(f"      - {name}: {err}")
    print(f"   📁 输出目录: {OUTPUT_DIR}")
    print("=" * 55)

    # ── 可选：导入 TIA 编译 ──
    if do_compile and results['ok']:
        print()
        print("🔌 导入 TIA Portal + 编译...")
        _import_and_compile([r[2] for r in results['ok']])

    return 0 if not results['error'] else 1


def _import_and_compile(scl_paths: list):
    """将所有 IO_Map SCL 导入 TIA Portal 并编译"""
    from tia_session import tia_session
    from Siemens.Engineering.SW.ExternalSources import GenerateBlockOption
    from Siemens.Engineering.Compiler import ICompilable

    with tia_session() as (project, plc_sw):
        if not plc_sw:
            print("❌ 未找到 PLC 设备")
            return

        ext_group = plc_sw.ExternalSourceGroup
        if ext_group is None:
            print("❌ ExternalSourceGroup 不可用")
            return

        imported = 0
        for scl_path in scl_paths:
            scl_name = os.path.basename(scl_path)
            try:
                # 清理旧源
                for es in list(ext_group.ExternalSources):
                    if str(es.Name) == scl_name:
                        es.Delete()
                ext_source = ext_group.ExternalSources.CreateFromFile(scl_name, scl_path)
                blocks = ext_source.GenerateBlocksFromSource(
                    getattr(GenerateBlockOption, 'None'))
                imported += 1
                print(f"   ✅ {scl_name} → {blocks.Count} 个块")
            except Exception as e:
                print(f"   ❌ {scl_name}: {e}")

        print(f"   📦 共导入 {imported} 个 SCL 文件")

        compiler = plc_sw.GetService[ICompilable]()
        cr = compiler.Compile()
        status = '✅' if cr.State.ToString() == 'Success' else f'⚠ State={cr.State}'
        print(f"   📦 编译: {status}, Errors={cr.ErrorCount}, Warnings={cr.WarningCount}")


if __name__ == '__main__':
    sys.exit(main())
