"""
最终诊断：导出标签表 XML 格式
每次都生成唯一名避免冲突，跑完关 TIA
"""
import sys, ctypes, os, datetime
if not ctypes.windll.shell32.IsUserAnAdmin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 1)
    sys.exit(0)

import clr
clr.AddReference(r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
clr.AddReference(r'D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
from Siemens.Engineering import TiaPortal, TiaPortalMode
from Siemens.Engineering.HW.Features import SoftwareContainer
from System.IO import FileInfo

TIA_PROJECT = r'D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18'
uid = datetime.datetime.now().strftime('%H%M%S')
tia = TiaPortal(TiaPortalMode.WithUserInterface)
try:
    project = tia.Projects.Open(FileInfo(TIA_PROJECT))
    plc_sw = None
    for device in project.Devices:
        for item in device.DeviceItems:
            try:
                c = item.GetService[SoftwareContainer]()
                if c and c.Software and 'PlcSoftware' in c.Software.GetType().FullName:
                    plc_sw = c.Software; break
            except: pass
        if plc_sw: break

    grp = plc_sw.TagTableGroup

    # 创建表（唯一名避免冲突）
    table = grp.TagTables.Create(f'_Diag_{uid}')
    print(f'✅ 创建表: {table.Name}')
    tags_coll = table.Tags

    # 加两条唯名标签
    tags_coll.Create(f'TagA_{uid}', 'Bool', '%M0.0')
    tags_coll.Create(f'TagB_{uid}', 'Bool', '%M0.1')
    print('✅ 已创建 2 条标签')

    # 导出 XML（唯一路径）
    xml_path = rf'D:\TIA FANG ZHEN\_diag_{uid}.xml'
    if os.path.exists(xml_path):
        os.remove(xml_path)
    from Siemens.Engineering import ExportOptions
    table.Export(FileInfo(xml_path), getattr(ExportOptions, 'None'))
    print(f'✅ 导出 XML: {xml_path}')

    with open(xml_path, 'r', encoding='utf-8') as f:
        xml = f.read()
    print(f'XML 大小: {len(xml)} chars')
    print()
    print('=== XML 内容 ===')
    print(xml)

    # 查看 Import 方法签名
    print('\n=== Import 方法签名 ===')
    from Siemens.Engineering.SW.Tags import PlcTagTableComposition
    import System
    from System.Reflection import BindingFlags
    for asm in System.AppDomain.CurrentDomain.GetAssemblies():
        if 'Siemens.Engineering' in asm.FullName:
            for t in asm.GetExportedTypes():
                if 'PlcTagTableComposition' in t.Name:
                    for m in t.GetMethods():
                        if 'Import' in m.Name:
                            ps = [f'{p.Name}:{p.ParameterType.Name}' for p in m.GetParameters()]
                            print(f'  {m.Name}({", ".join(ps)}) -> {m.ReturnType.Name}')
                    break

    project.Save()

except Exception as e:
    print(f'❌ 错误: {e}')
    import traceback; traceback.print_exc()
finally:
    tia.Dispose()
    print('\n✅ TIA Portal 已关闭')
