"""
诊断：如何设置 PlcTag 的 Comment
"""
import sys, ctypes
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
    table = grp.TagTables.Create('_DiagTest3')
    tags_coll = table.Tags

    entry = tags_coll.Create('TestTag', 'Bool', '%M0.0')
    print(f'创建成功: {entry.Name}')

    # 方法1: SetAttribute
    print('\n尝试 SetAttribute:')
    try:
        entry.SetAttribute('Comment', '中文测试')
        print(f'  SetAttribute 成功: {entry.Comment}')
    except Exception as e:
        print(f'  SetAttribute 失败: {e}')

    # 方法2: SetAttributes (Dictionary)
    print('\n尝试 SetAttributes:')
    try:
        import System.Collections.Generic as Gen
        attrs = Gen.Dictionary[str, str]()
        attrs['Comment'] = '中文测试2'
        entry.SetAttributes(attrs)
        print(f'  SetAttributes 成功: {entry.Comment}')
    except Exception as e:
        print(f'  SetAttributes 失败: {e}')

    # 方法3: 直接查看 GetAttribute 支持哪些属性
    print('\n查看支持的属性:')
    try:
        # GetAttributeInfos 返回支持的属性列表
        infos = entry.GetAttributeInfos()
        print(f'  属性数: {len(infos)}')
        for info in infos[:20]:
            print(f'  - {info}')
    except Exception as e:
        print(f'  GetAttributeInfos 失败: {e}')

    # 方法4: 试试 GetAttributes
    print('\n尝试 GetAttributes:')
    try:
        attrs = entry.GetAttributes()
        print(f'  GetAttributes 返回: {type(attrs)}')
        # 尝试遍历
        for k,v in attrs.items():
            print(f'  {k} = {v}')
    except Exception as e:
        print(f'  GetAttributes 失败: {e}')

    # 清理
    grp.TagTables.Delete(table)
    project.Save()
    print('\n✅ 诊断完成')

except Exception as e:
    print(f'❌ 错误: {e}')
    import traceback; traceback.print_exc()
finally:
    tia.Dispose()
