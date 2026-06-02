import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from plcsim_api import get_instances

instances = get_instances()
print("=== PLCSIM 实例状态 ===")
if not instances:
    print("  (没有实例)")
else:
    for i in instances:
        print(f"  名称: {i['name']}")
        print(f"  状态: {i['state']}")
        print(f"  CPU: {i.get('cpu_type','?')}")
        print(f"  ID: {i['id']}")
        print()
