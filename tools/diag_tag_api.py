"""
诊断 TIA Portal Tag API - 打开项目并显示 Tags 集合的方法
用法: python tools/diag_tag_api.py
"""
import sys, os, ctypes

# 自动提权
if not ctypes.windll.shell32.IsUserAnAdmin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 1
    )
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
    # 找 PLC
    plc_sw = None
    for device in project.Devices:
        for item in device.DeviceItems:
            try:
                c = item.GetService[SoftwareContainer]()
                if c and c.Software and 'PlcSoftware' in c.Software.GetType().FullName:
                    plc_sw = c.Software
                    break
            except:
                pass
        if plc_sw:
            break

    # 创建临时标签表测试
    grp = plc_sw.TagTableGroup
    table = grp.TagTables.Create('_DiagTest')
    print(f'表名: {table.Name}')
    print(f'Tags 类型: {type(table.Tags)}')
    print(f'Tags dir: {[x for x in dir(table.Tags) if not x.startswith("_")]}')
    
    # 尝试 Create
    tags_coll = table.Tags
    print(f'\n尝试 Create():')
    try:
        entry = tags_coll.Create('TestTag', 'Bool', '%M0.0')
        print(f'  3参数 Create 成功: {entry}')
        print(f'  entry 类型: {type(entry)}')
    except Exception as e:
        print(f'  3参数 Create 失败: {e}')
    
    try:
        entry2 = tags_coll.Create()
        print(f'  0参数 Create 成功: {entry2}')
        if entry2:
            entry2.Name = 'TestTag2'
            entry2.DataTypeName = 'Bool'
            entry2.AbsoluteAddress = '%M0.1'
            entry2.Comment = '测试'
            print(f'  属性设置成功')
    except Exception as e:
        print(f'  0参数 Create 失败: {e}')
    
    # 查看已有条目
    print(f'\n已有标签数: {len(list(tags_coll))}')
    for t in tags_coll:
        print(f'  name={t.Name}, type={t.DataTypeName}, addr={t.AbsoluteAddress}, comment={t.Comment}')
        break  # 只显示第一个
    
    # 清理
    grp.TagTables.Delete(table)
    project.Save()
    print(f'\n✅ 诊断完成，已清理测试表')

except Exception as e:
    print(f'❌ 错误: {e}')
    import traceback
    traceback.print_exc()
finally:
    tia.Dispose()
