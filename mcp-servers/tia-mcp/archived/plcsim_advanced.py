"""
PLCSIM Advanced 辅助工具：启动、配置虚拟网卡、检查状态。

用法:
  python plcsim_advanced.py start           # 启动 PLCSIM Advanced GUI
  python plcsim_advanced.py adapter         # 检查/配置虚拟以太网适配器
  python plcsim_advanced.py status          # 检查实例状态（ping + 端口）
  python plcsim_advanced.py kill            # 清理所有 PLCSIM 进程
"""
import sys, os, subprocess, time

from config_loader import cfg

ADV_DIR = cfg.simulation.advanced_install_dir
ADV_EXE = os.path.join(ADV_DIR, 'bin', 'Siemens.Simatic.PlcSim.Advanced.UserInterface.exe')
ADAPTER_EXE = os.path.join(ADV_DIR, 'bin', 'Siemens.Simatic.PlcSim.Advanced.AdapterConfigurator.exe')
PLC_IP = cfg.simulation.advanced.plc_ip


def start_gui():
    """启动 PLCSIM Advanced 主界面"""
    if not os.path.exists(ADV_EXE):
        print(f'❌ PLCSIM Advanced 未找到: {ADV_EXE}')
        return 1
    print(f'🚀 启动: {ADV_EXE}')
    subprocess.Popen([ADV_EXE])
    print()
    print('─── 在 GUI 中操作 ───')
    print(f'1. Start Virtual SIMATIC PLC (或 + New Instance)')
    print(f'2. PLC Family: SIMATIC S7-1500')
    print(f'3. PLC Type:   CPU 1511-1 PN (或你项目中的型号)')
    print(f'4. Name:        AI_PLC_Test')
    print(f'5. IP Address:  {PLC_IP}')
    print(f'6. Subnet:      255.255.255.0')
    print(f'7. → Start')
    print()
    print(f'   状态灯变绿色 RUN 即为就绪')
    return 0


def check_adapter():
    """检查虚拟以太网适配器"""
    # 运行适配器配置工具
    print(f'🔧 检查 PLCSIM Virtual Ethernet Adapter...')
    print()

    if os.path.exists(ADAPTER_EXE):
        print(f'   适配器配置工具: {ADAPTER_EXE}')
        print(f'   请手动检查 PLCSIM Virtual Ethernet Adapter 是否已启用')
        print(f'   如未启用，运行此工具配置')
    else:
        print(f'   ⚠ 适配器配置工具未找到')

    # 检查网卡
    r = subprocess.run('ipconfig', capture_output=True, text=True)
    if 'PLCSIM' in r.stdout or 'Siemens' in r.stdout:
        print('   ✅ 检测到 PLCSIM/Siemens 虚拟网卡')
    else:
        print('   ⚠ 未检测到虚拟网卡，启动 PLCSIM Advanced 后会自动创建')
        print(f'   手动配置: {ADAPTER_EXE}')

    return 0


def check_status():
    """检查 PLCSIM Advanced 是否可达"""
    print(f'🔍 检查 {PLC_IP}...')
    r = subprocess.run(['ping', PLC_IP, '-n', '1', '-w', '1000'],
                      capture_output=True, text=True)
    if r.returncode == 0:
        print(f'   ✅ {PLC_IP} 可达')
        ttl_line = [l for l in r.stdout.split('\n') if 'TTL' in l or 'ttl' in l]
        if ttl_line:
            print(f'      {ttl_line[0].strip()}')
    else:
        print(f'   ❌ {PLC_IP} 无法 ping 通')
        print()
        print('   请先: python plcsim_advanced.py start')
        print('   然后在 GUI 中创建实例')
        return 1

    # 检查端口 102
    print(f'   检查端口 {cfg.simulation.advanced.port}...')
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((PLC_IP, cfg.simulation.advanced.port))
        print(f'   ✅ 端口 {cfg.simulation.advanced.port} 开放 (S7 通信正常)')
        s.close()
    except Exception:
        print(f'   ⚠ 端口 {cfg.simulation.advanced.port} 不通（可能 PLC 未在 RUN）')

    return 0


def kill_all():
    """强杀所有 PLCSIM 进程（解决 Port 102 冲突）"""
    killed = []
    for name in ['S7-PLCSIM*', 'S7PlcSim*', 'Siemens.Simatic.PlcSim*']:
        r = subprocess.run(
            f'tasklist /fi "IMAGENAME eq {name}" /fo csv /nh',
            shell=True, capture_output=True, text=True, encoding='gbk', errors='replace')
        for line in (r.stdout or '').strip().split('\n'):
            if line:
                proc = line.replace('"', '').split(',')[0].strip()
                if proc:
                    subprocess.run(['taskkill', '/f', '/im', proc], capture_output=True)
                    killed.append(proc)

    if killed:
        print(f'🗑 已结束: {", ".join(killed)}')
    else:
        print('✅ 没有找到运行中的 PLCSIM 进程')
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 0

    cmd = sys.argv[1]
    if cmd == 'start':
        return start_gui()
    elif cmd == 'adapter':
        return check_adapter()
    elif cmd == 'status':
        return check_status()
    elif cmd == 'kill':
        return kill_all()
    else:
        print(f'未知命令: {cmd}')
        print(__doc__)
        return 1


if __name__ == '__main__':
    sys.exit(main())
