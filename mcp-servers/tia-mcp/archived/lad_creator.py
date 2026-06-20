"""
AI → SimaticML XML → TIA Portal LAD 块 全自动管道

用法:
    python lad_creator.py <生成器参数>
    
现在支持:
    python lad_creator.py cart3cycle
        → 生成 AutoCart3Cycle LAD 块导入 demo 项目
"""

import subprocess
import json
import sys
import os

# ─── 路径 ───
CARTGEN_DIR = os.path.join(os.path.dirname(__file__), "CartGen")
CARTGEN_DLL = os.path.join(CARTGEN_DIR, "bin", "Release", "net8.0", "CartGen.dll")
TIA_PROJECT = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18"
LAD_XML = r"D:\TIA FANG ZHEN\cart3cycle_lad.xml"


def main():
    if len(sys.argv) < 2:
        print("用法: python lad_creator.py cart3cycle")
        return 1

    command = sys.argv[1]

    if command == "cart3cycle":
        return generate_cart3cycle()
    else:
        print("未知命令:", command)
        return 1


def generate_cart3cycle():
    """生成小车往复3次 LAD 块"""
    print("=" * 50)
    print("🚗 材料小车 — 往复3次停止")
    print("=" * 50)

    # 步骤1: 编译 CartGen（如果 DLL 不存在）
    if not os.path.exists(CARTGEN_DLL):
        print("[1/4] 编译 CartGen...")
        r = subprocess.run(
            ["dotnet", "build", "-c", "Release", CARTGEN_DIR],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            print("❌ 编译失败:", r.stderr)
            return 1
        print("   ✅ 编译成功")

    # 步骤2: 生成 SimaticML XML（直接跑编译好的 DLL，避免 dotnet run 输出编译警告）
    print("[2/4] 生成 LAD XML...")
    template_json = os.path.join(os.path.dirname(__file__), "templates", "cart3cycle.json")
    dll_path = os.path.join(CARTGEN_DIR, "bin", "Release", "net8.0", "CartGen.dll")
    r = subprocess.run(
        ["dotnet", "exec", dll_path, template_json, LAD_XML],
        capture_output=True
    )
    out = r.stdout.decode('utf-8', errors='ignore')
    err = r.stderr.decode('utf-8', errors='ignore')
    # 只打印 ✅ 那行
    for line in err.split("\n"):
        if "✅" in line:
            print("   ", line.strip())
    if r.returncode != 0:
        print("❌ 生成失败:", err[:500])
        return 1

    # 步骤3: 导入 TIA Portal
    print("[3/4] 导入 TIA Portal...")
    import clr, System
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    
    from Siemens.Engineering import TiaPortal, TiaPortalMode, ImportOptions
    from Siemens.Engineering.SW import SWImportOptions
    from System.IO import FileInfo

    tia = TiaPortal(TiaPortalMode.WithoutUserInterface)
    project = tia.Projects.Open(FileInfo(TIA_PROJECT))
    print("   项目:", project.Name)

    # 找 PLC
    plc_sw = None
    for device in project.Devices:
        for item in device.DeviceItems:
            asm = System.Reflection.Assembly.LoadFrom(
                r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
            sc_type = asm.GetType('Siemens.Engineering.HW.Features.SoftwareContainer')
            for m in item.GetType().GetMethods():
                if m.Name == 'GetService' and m.IsGenericMethodDefinition:
                    container = m.MakeGenericMethod(sc_type).Invoke(item, None)
                    if container:
                        sw = container.GetType().GetProperty('Software').GetValue(container, None)
                        if sw and 'PlcSoftware' in sw.GetType().FullName:
                            plc_sw = sw
                            break
    if not plc_sw:
        print("❌ 未找到 PLC 设备")
        tia.Dispose()
        return 1

    # 清洗 XML：去掉 <Text /> 为空的 MultilingualTextItem
    import re
    with open(LAD_XML, 'r', encoding='utf-8') as f:
        xml = f.read()
    # 匹配 <MultilingualTextItem ...><AttributeList><Culture>...</Culture><Text /></AttributeList></MultilingualTextItem>
    xml = re.sub(
        r'<MultilingualTextItem[^>]*>\s*<AttributeList>\s*<Culture>[^<]*</Culture>\s*<Text\s*/>\s*</AttributeList>\s*</MultilingualTextItem>\s*',
        '', xml)
    with open(LAD_XML, 'w', encoding='utf-8') as f:
        f.write(xml)

    # 导入 XML
    try:
        plc_sw.BlockGroup.Blocks.Import(
            FileInfo(LAD_XML),
            ImportOptions.Override,
            SWImportOptions(2)
        )
        print("   ✅ XML 导入成功")

        # 编译（用反射调 GetService）
        comp_type = asm.GetType('Siemens.Engineering.Compiler.ICompilable')
        compiler = None
        for m in plc_sw.GetType().GetMethods():
            if m.Name == 'GetService' and m.IsGenericMethodDefinition:
                compiler = m.MakeGenericMethod(comp_type).Invoke(plc_sw, None)
                break
        if compiler:
            result = compiler.Compile()
            state = result.GetType().GetProperty('State').GetValue(result, None)
            errors = result.GetType().GetProperty('ErrorCount').GetValue(result, None)
            print('   ✅ 编译完成: State=%s, Errors=%s' % (state, errors))
        else:
            print('   ⚠️ 编译服务不可用，跳过编译')

        project.Save()
        print("   ✅ 项目已保存")

        # 列出所有块
        print()
        print("   项目中的块:")
        for b in plc_sw.BlockGroup.Blocks:
            try:
                print("     - %s (%s)" % (b.Name, b.ProgrammingLanguage))
            except:
                pass

    except Exception as e:
        print("❌ 导入失败:", str(e)[:300])
        tia.Dispose()
        return 1

    tia.Dispose()
    print()
    print("✅ 全部完成！打开 TIA Portal 就能看到 AutoCart3Cycle LAD 块")
    return 0


if __name__ == "__main__":
    sys.exit(main())
