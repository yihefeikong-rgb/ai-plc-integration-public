"""
诊断 PlcTag 的属性 - 找出正确的属性名
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
import Siemens.Engineering.SW.Tags as Tags

# 打印 PlcTag 的所有可写属性
from Siemens.Engineering.SW.Tags import PlcTag
print('=== PlcTag 的成员 ===')
for name in dir(PlcTag):
    if not name.startswith('_') and name not in ['Equals','GetHashCode','GetType','ToString']:
        print(f'  {name}')

# 检查 PlcTagComposition 的 Create 签名
print()
print('=== PlcTagComposition.Create 详情 ===')
comp = Tags.PlcTagComposition
# 查找 Create 的重载
import System
from System.Reflection import BindingFlags
bf = BindingFlags.Public | BindingFlags.Instance
# 获取 .NET Type 对象
t_type = comp.GetType() if hasattr(comp, 'GetType') else type(comp)
# 通过 PlcTagTable 的类型找
table_type = Tags.PlcTagTable
print(f'PlcTagTable type: {table_type}')

# 直接通过创建实例来测试
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
    table = grp.TagTables.Create('_DiagTest2')
    tags_coll = table.Tags
    
    # 创建一个标签
    entry = tags_coll.Create('TestTag', 'Bool', '%M0.0')
    print(f'\n创建了一个 PlcTag 实例，检查属性:')
    
    # 列出所有可读写属性
    for name in dir(entry):
        if not name.startswith('_') and name not in ['Equals','GetHashCode','GetType','ToString','Finalize','MemberwiseClone']:
            if name in ['Name', 'Comment'] or 'Address' in name or 'DataType' in name:
                try:
                    val = getattr(entry, name)
                    print(f'  {name} = {val!r}')  # !r uses repr
                except:
                    pass
    
    # 尝试设置 Comment
    print('\n尝试设置 Comment:')
    try:
        entry.Comment = '中文测试注释'
        print(f'  Comment 设置成功: {entry.Comment}')
    except Exception as e:
        print(f'  Comment 设置失败: {e}')
    
    # 打印所有属性
    print('\n所有可读属性:')
    for name in sorted(dir(entry)):
        if not name.startswith('_') and name not in ['Equals','GetHashCode','GetType','ToString','Finalize','MemberwiseClone']:
            try:
                val = getattr(entry, name)
                print(f'  {name} = {val!r}')
            except:
                pass

    # 清理
    grp.TagTables.Delete(table)
    project.Save()
    print('\n✅ 诊断完成')

except Exception as e:
    print(f'❌ 错误: {e}')
    import traceback; traceback.print_exc()
finally:
    tia.Dispose()
