"""
测试 restore_instance 流程：
1. 用 restore_instance 从 golden.zip 恢复一个新实例
2. 验证能正常 Run
3. 清理
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

GOLDEN_ZIP = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\factory_io1_golden.zip"
STORAGE = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\test_restore_storage"

if not os.path.exists(GOLDEN_ZIP):
    print(f"❌ golden.zip 不存在: {GOLDEN_ZIP}")
    sys.exit(1)

from plcsim_api import restore_instance, stop_instance, get_instances

print("=== 测试 restore_instance ===")
print(f"golden: {GOLDEN_ZIP}")

try:
    inst = restore_instance(
        name="test_restore",
        golden_zip=GOLDEN_ZIP,
        storage_path=STORAGE,
        ip="10.0.0.200",
        cpu_type="1511",
        interface="softbus",
    )
    print(f"\n✅ restore 成功！状态: {inst.OperatingState}")

except Exception as e:
    print(f"\n❌ restore 失败: {e}")
    sys.exit(1)

finally:
    # 清理
    print("\n=== 清理 ===")
    instances = get_instances()
    print(f"当前实例: {[i['name'] for i in instances]}")
