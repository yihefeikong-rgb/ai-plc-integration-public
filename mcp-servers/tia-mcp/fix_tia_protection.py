"""
通过 TIA Openness API 修改 PLC 保护设置：
  1. Full access (no protection)
  2. Permit access with PUT/GET communication
"""
import sys, os, time

PROJECT_PATH = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18"
TIA_DLL = r"D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll"
TIA_CONTRACT = r"D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll"

import clr
clr.AddReference(TIA_DLL)
clr.AddReference(TIA_CONTRACT)

from Siemens.Engineering import TiaPortal, TiaPortalMode
from Siemens.Engineering.Compiler import ICompilable
from Siemens.Engineering.HW.Features import PlcAccessLevelProvider
from Siemens.Engineering.HW import PlcProtectionAccessLevel
from System.IO import FileInfo


def fix_plc(plc_item):
    """修改单个 PLC 的保护设置。"""
    name = plc_item.Name
    type_str = str(plc_item.TypeIdentifier)
    
    try:
        prot = plc_item.GetService[PlcAccessLevelProvider]()
        if prot is None:
            print(f"  {name}: PlcAccessLevelProvider 返回 None")
            return False
        
        # 1. 设置完全访问
        old_level = prot.PlcProtectionAccessLevel
        prot.PlcProtectionAccessLevel = PlcProtectionAccessLevel.FullAccess
        new_level = prot.PlcProtectionAccessLevel
        print(f"  {name}: 访问级别 {old_level} → {new_level}")
        
        # 2. 启用 PUT/GET (CommunicationMode=2 通常表示允许 PUT/GET)
        try:
            old_mode = prot.GetAttribute("CommunicationMode")
            prot.SetAttribute("CommunicationMode", 2)
            print(f"  {name}: CommunicationMode {old_mode} → 2")
        except Exception as e:
            print(f"  {name}: CommunicationMode 设置失败: {e}")
            # 尝试其他属性名
            for attr_name in ["PutGet", "AllowPutGet", "Communication", "PGandPC"]:
                try:
                    old_val = prot.GetAttribute(attr_name)
                    prot.SetAttribute(attr_name, True)
                    print(f"  {name}: {attr_name} {old_val} → True")
                except:
                    pass
        
        return True
    except Exception as e:
        print(f"  {name}: 失败 {e}")
        return False


def main():
    print(f"打开项目: {PROJECT_PATH}")
    tia = TiaPortal(TiaPortalMode.WithoutUserInterface)
    try:
        project = tia.Projects.Open(FileInfo(PROJECT_PATH))
        print("项目已打开")
        
        # 遍历所有设备
        print("\n查找 PLC 设备:")
        for dev in project.Devices:
            for item in dev.DeviceItems:
                type_str = str(item.TypeIdentifier)
                if "PLC_" in item.Name or "CPU" in item.Name:
                    print(f"  找到: {item.Name} ({type_str})")
                    fix_plc(item)
        
        # 编译
        print("\n编译...")
        all_ok = True
        for dev in project.Devices:
            try:
                comp = dev.GetService[ICompilable]()
                if comp:
                    r = comp.Compile()
                    print(f"  {dev.Name}: {r.State} E={r.ErrorCount} W={r.WarningCount}")
                    if r.ErrorCount > 0:
                        all_ok = False
            except Exception as e:
                print(f"  {dev.Name}: {e}")
                all_ok = False
        
        project.Save()
        
        if all_ok:
            print("\n✅ 项目已保存，设置已修改")
            print("\n" + "="*60)
            print("下一步（手动操作）：")
            print("="*60)
            print("1. 管理员身份运行 TIA Portal")
            print("2. 打开 demo.ap18")
            print("3. 右键 PLC_2 (S7-1500) → Download to device")
            print("   → Hardware and software configuration")
            print("4. 下载完成后 CPU 会自动 RUN")
            print("5. 启动当前 PLCSIM keeper，然后：")
            print("6. 打开 Factory IO（管理员）→ 驱动选 Siemens S7-1200/1500")
            print("7. IP: 10.0.0.1，网卡: Siemens PLCSIM Virtual Eth. Adapter")
            print("8. 点 Connect")
            print("="*60)
        else:
            print("\n⚠ 编译有错误，请检查")
    
    finally:
        try:
            project.Close()
        except:
            pass
        try:
            tia.Dispose()
        except:
            pass
        import subprocess
        for f in ['S7*', 'Tia*']:
            subprocess.run(f'taskkill /f /im {f} >nul 2>nul', shell=True)


if __name__ == "__main__":
    main()
