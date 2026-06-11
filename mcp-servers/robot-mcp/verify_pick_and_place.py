"""
P4 实测验收 — Pick & Place (Basic) 场景验证脚本

用法:
    python mcp-servers/robot-mcp/test_pick_and_place.py

步骤:
  1. 先启动 PLCSIM Advanced + Factory I/O (Pick & Place 场景)
  2. 运行本脚本
  3. 脚本自动检测连接、探索地址空间、测试 I/O
  4. 输出诊断结果和建议
"""

import sys
import time
import asyncio
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROBOT_DIR = Path(__file__).parent
PROJECT_ROOT = ROBOT_DIR.parent.parent
sys.path.insert(0, str(ROBOT_DIR))

PLC_IP = "192.168.0.1"
OPCUA_PORT = 4840
OPCUA_URL = f"opc.tcp://{PLC_IP}:{OPCUA_PORT}"


def print_header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_result(name: str, ok: bool, detail: str = ""):
    mark = "✅" if ok else "❌"
    print(f"  {mark} {name}")
    if detail:
        print(f"     {detail}")


async def test_opcua_connectivity():
    """测试 OPC UA 连接"""
    print_header("1. OPC UA 连接测试")
    print(f"   端点: {OPCUA_URL}")

    try:
        from asyncua import Client
        client = Client(url=OPCUA_URL)
        await client.connect()
        print_result("OPC UA 连接成功", True)
    except Exception as e:
        print_result("OPC UA 连接失败", False, str(e)[:200])
        print("\n  可能原因:")
        print("    - PLCSIM 未启动或实例未 RUN")
        print("    - PLC 程序中未启用 OPC UA 服务器")
        print("    - IP 地址不匹配 (当前设 192.168.0.1)")
        print("    - 防火墙阻止端口 4840")
        print("\n  建议方案 (二选一):")
        print("    A) 在 TIA Portal 中启用 OPC UA: CPU 属性 → OPC UA → 勾选激活")
        print("    B) 改用 snap7 (S7 协议), 无需配置")
        return None

    return client


async def explore_opcua_nodes(client):
    """探索 OPC UA 地址空间，寻找 I/O 节点"""
    print_header("2. OPC UA 地址空间探索")
    
    try:
        root = client.get_objects_node()
        children = await root.get_children()
        print(f"   根节点下 {len(children)} 个子节点")
        
        # 递归探索，最多 3 层，寻找 PLC/I/O 相关节点
        async def explore(node, depth=0, max_depth=3):
            if depth > max_depth:
                return []
            results = []
            try:
                browse_name = await node.read_browse_name()
                node_name = browse_name.Name
                node_id = str(node)
                
                # 过滤感兴趣的节点
                keywords = ['PLC', 'I', 'Q', 'INPUT', 'OUTPUT', 'PROGRAM', 'tag']
                if any(k in node_name.upper() for k in keywords):
                    try:
                        val = await node.read_value()
                        results.append((node_id, node_name, str(val)[:50], depth))
                    except:
                        results.append((node_id, node_name, '(结构节点)', depth))
                
                subs = await node.get_children()
                for sub in subs:
                    results.extend(await explore(sub, depth + 1, max_depth))
            except:
                pass
            return results
        
        found = await explore(root, 0, 4)
        
        if found:
            print(f"\n   找到 {len(found)} 个相关节点:")
            for node_id, name, val, depth in found[:30]:
                indent = "  " * (depth + 1)
                print(f"  {indent}{'─' if depth > 0 else ''}{name:30s} = {val:20s}  ({node_id[:60]})")
        else:
            print("   未找到 I/O 相关节点")
            print("   建议: 检查 TIA Portal 中 OPC UA 配置是否正确")
        
        return found
    except Exception as e:
        print_result("地址空间探索失败", False, str(e)[:200])
        return []


async def test_snap7_connectivity():
    """测试 S7 (snap7) 连接作为替代"""
    print_header("3. S7/snap7 连接测试 (备选)")
    
    try:
        import snap7
        client = snap7.client.Client()
        client.connect(PLC_IP, 0, 1)  # rack=0, slot=1 for S7-1500
        if client.get_connected():
            print_result("snap7 连接成功", True, f"PLC: {PLC_IP}, rack=0, slot=1")
            
            # 尝试读取 I0.0 (process inputs)
            try:
                # Read process input area (area 0x81 = inputs)
                data = client.read_area(0x81, 0, 0, 2)  # 2 bytes = 16 I points
                print(f"\n   %I0.0-1.7 原始数据: {data.hex()}")
                for bit in range(16):
                    byte_idx = bit // 8
                    bit_idx = bit % 8
                    val = bool(data[byte_idx] & (1 << bit_idx))
                    print(f"     I{bit // 8}.{bit % 8} = {int(val)}")
                print_result("读取 %I 成功", True)
            except Exception as e:
                print_result("读取 %I 失败", False, str(e)[:100])
            
            client.disconnect()
            return True
        else:
            print_result("snap7 未连接", False)
            return False
    except ImportError:
        print("   snap7 未安装 (pip install python-snap7)")
        print_result("snap7 不可用", False, "请安装: pip install python-snap7")
        return False
    except Exception as e:
        print_result("snap7 连接失败", False, str(e)[:200])
        return False


async def test_server_import():
    """测试 robot-mcp 导入"""
    print_header("4. robot-mcp 导入验证")
    try:
        from server import mcp, go_home, pick_item, place_item, move_arm_to, get_status, control_conveyor, run_pick_cycle, IO_MAP
        print_result("导入成功", True, f"IO_MAP 含 {len(IO_MAP)} 个 I/O 点")
        
        # 检查 IO_MAP 中的节点路径
        print("\n   当前 IO_MAP 节点路径:")
        for name, info in IO_MAP.items():
            path = info.get("node", "N/A")
            print(f"     {name:20s} → {path}")
        return True
    except Exception as e:
        print_result("导入失败", False, str(e)[:200])
        return False


async def main():
    print()
    print(f"{'=' * 60}")
    print(f"  P4 实测验收 — Pick & Place (Basic)")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")
    
    print("\n⚠️  请先确保:")
    print("  1. PLCSIM Advanced V8.0 已启动, 实例 factoryio 为 RUN 状态")
    print("  2. Factory I/O 已打开, 加载 'Pick & Place (Basic)' 场景")
    print("  3. F4 → S7-PLCSIM 驱动 → 已连接 (自动连接或手动 Connect)")
    print("  4. 按空格键启动场景")
    print()
    input("   准备好后按 Enter 继续...")
    
    # 1. OPC UA
    client = await test_opcua_connectivity()
    opcua_ok = client is not None
    
    if client:
        # 2. 探索地址空间
        found = await explore_opcua_nodes(client)
        if found:
            print("\n📝 请根据上面的节点路径更新 IO_MAP:")
            print("   编辑 mcp-servers/robot-mcp/server.py 中的 IO_MAP")
            print("   将 node 路径替换为实际值 (如 ns=4;s=|var|PLC.PROGRAM...)")
        await client.disconnect()
    
    # 3. snap7 备选
    snap7_ok = await test_snap7_connectivity()
    
    # 4. 导入检查
    await test_server_import()
    
    # 汇总
    print_header("诊断汇总")
    print_result(f"OPC UA 连接 ({OPCUA_URL})", opcua_ok)
    print_result("snap7 连接 (备选)", snap7_ok)
    
    if not opcua_ok and not snap7_ok:
        print("\n⚠️  两种连接方式均不可用。请确保:")
        print("  1. PLCSIM 正在运行 (GUI 中确认绿灯)")
        print("  2. IP 地址匹配 (PLCSIM GUI 中显示的 IP)")
        print("  3. 虚拟网卡已安装 (Siemens PLCSIM Virtual Ethernet Adapter)")
    elif opcua_ok:
        print("\n✅ OPC UA 可用！更新 IO_MAP 中的节点路径后即可运行 robot-mcp")
    elif snap7_ok:
        print("\n✅ snap7 可用！可考虑给 robot-mcp 添加 snap7 后端")
    
    print(f"\n{'=' * 60}")
    print(f"  诊断完成")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
