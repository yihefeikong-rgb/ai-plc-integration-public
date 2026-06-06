#!/usr/bin/env python3
"""
P3 下载脚本 — V21 → PLCSIM → Factory I/O

关键流程：
  1. 恢复 PLCSIM golden → RUN + GUI（外部供 FIO 连接）
  2. API 启动唯一 V21 → 打开项目 → 编译
  3. uiautomation 切换项目视图 → 点击 PLC 程序块（按钮才变可用）
     → 直接点击下载（不需启动仿真！PLCSIM 已处于 STOP 待下载状态）
  4. 启动 Factory I/O

用法:
    python p3_flow.py                       # 完整流程
    python p3_flow.py --download-only       # 仅下载
"""
import sys, os, subprocess, time, ctypes

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TIA_MCP_DIR = os.path.join(SCRIPT_DIR, "mcp-servers", "tia-mcp")
GOLDEN_ZIP = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo_V21\factory_io1_golden.zip"
STORAGE_PATH = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo_V21\plcsim_storage"
PROJECT_PATH = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo_V21\demo_V21.ap21"
FIO_EXE = r"D:\Factory IO\Factory IO.exe"

GREEN='\033[92m'; YELLOW='\033[93m'; RED='\033[91m'; BLUE='\033[94m'; RESET='\033[0m'
def log(msg, l="info"):
    e={"ok":"✅","warn":"🟡","error":"❌","info":"📋","step":"▶","wait":"⏳"}.get(l,"•")
    c={"ok":GREEN,"warn":YELLOW,"error":RED,"info":BLUE}.get(l,"")
    print(f"{c}{e} {msg}{RESET}")

def sep(t): print(f"\n{BLUE}{'='*56}{RESET}\n{BLUE}  {t}{RESET}\n{BLUE}{'='*56}{RESET}\n")

# 保持 API 引用的全局容器（防止 GC 关闭 V21）
_keepalive = []

def find_ctrl(ctrl, name_substr, depth=15):
    """在控件树中递归搜索名称包含子串的控件"""
    if depth < 0: return None
    try:
        if name_substr in (ctrl.Name or ''): return ctrl
    except: pass
    try:
        for c in ctrl.GetChildren():
            r = find_ctrl(c, name_substr, depth-1)
            if r: return r
    except: pass
    return None

def find_ctrl_multi(ctrl, names, depth=12):
    """搜索匹配多个可能名称的控件"""
    if depth < 0: return None
    try:
        n = ctrl.Name or ''
        for s in names:
            if s in n: return ctrl
    except: pass
    try:
        for c in ctrl.GetChildren():
            r = find_ctrl_multi(c, names, depth-1)
            if r: return r
    except: pass
    return None

def click_in_tree(tia_win, name_substr):
    """在项目树中找到并点击指定名称的节点"""
    # 项目树通常在 HardwareNavigationFrame 或 ProjectNavigatorViewFrame 中
    tree = find_ctrl(tia_win, 'ProjectNavigatorViewFrame')
    if not tree:
        tree = find_ctrl(tia_win, 'HardwareNavigationFrame')
    if not tree:
        log("未找到项目树", "warn")
        return False
    
    node = find_ctrl(tree, name_substr)
    if node:
        node.Click()
        log(f"已点击 '{name_substr}'", "ok")
        time.sleep(2)
        return True
    else:
        log(f"树中未找到 '{name_substr}'", "warn")
        return False


# ═══════════════════════════════════════
#  步骤 1: PLCSIM
# ═══════════════════════════════════════
def step1_plcsim():
    """恢复 PLCSIM golden → STOP（黄色待下载状态，V21 才能扫描到）"""
    sep("步骤 1: PLCSIM 仿真（黄色 STOP 待下载状态）")
    sys.path.insert(0, TIA_MCP_DIR)
    from plcsim_api import restore_instance, get_instances, _ensure_user_interface
    # 无条件恢复为 STOP（auto_run=False 不调用 Run，实例停在 STOP 状态）
    inst = restore_instance(name='factoryio', golden_zip=GOLDEN_ZIP,
                            storage_path=STORAGE_PATH, ip='10.0.0.1',
                            interface='softbus', auto_run=False)
    log(f"PLCSIM: {inst.OperatingState}（黄色待下载，V21 可扫描）", "ok")
    _ensure_user_interface(); time.sleep(3)
    return True


# ═══════════════════════════════════════
#  步骤 2: 编译 + 下载
# ═══════════════════════════════════════
def step2_download():
    sep("步骤 2: 编译 + 下载到 PLCSIM")

    import uiautomation as ua

    # ── 清理残留 V21 ──
    log("清理 TIA Portal 残留进程...", "step")
    subprocess.run(['cmd.exe','/c','taskkill','/f','/im','Siemens.Automation.Portal.exe'],
                   capture_output=True, timeout=10)
    time.sleep(3)

    # ── API 启动唯一 V21 + 编译 ──
    log("加载 Openness DLL...", "step")
    sys.path.insert(0, TIA_MCP_DIR)
    from config_loader import cfg
    import clr
    td=cfg.tia.install_dir; tv=cfg.tia.version
    clr.AddReference(rf'{td}\PublicAPI\{tv}\net48\Siemens.Engineering.Base.dll')
    clr.AddReference(rf'{td}\PublicAPI\{tv}\net48\Siemens.Engineering.Step7.dll')
    clr.AddReference(rf'{td}\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode
    from Siemens.Engineering.Compiler import ICompilable
    from System.IO import FileInfo

    log("启动 TIA Portal V21（唯一实例）...", "step")
    tia = TiaPortal(TiaPortalMode.WithUserInterface)
    _keepalive.append(tia)
    log("V21 已启动", "ok")

    log("打开项目...", "step")
    proj = tia.Projects.Open(FileInfo(PROJECT_PATH))
    log(f"项目: {proj.Name}", "ok")
    _keepalive.append(proj)

    # 找 PLC 软件 → 编译
    from Siemens.Engineering.HW.Features import SoftwareContainer
    plc_sw = None
    for d in proj.Devices:
        for i in d.DeviceItems:
            try:
                c = i.GetService[SoftwareContainer]()
                if c and c.Software and 'PlcSoftware' in c.Software.GetType().FullName:
                    plc_sw = c.Software; break
            except: pass
        if plc_sw: break

    if plc_sw:
        log("编译中...", "step")
        comp = plc_sw.GetService[ICompilable]()
        cr = comp.Compile()
        log(f"Errors={cr.ErrorCount}, Warnings={cr.WarningCount}", "ok" if cr.ErrorCount==0 else "error")
        proj.Save()
    else:
        log("未找到 PLC 软件", "warn")

    # ── 等 V21 窗口出现 ──
    log("等待 V21 窗口（最长 60s）...", "wait")
    deadline = time.time() + 60
    tia_win = None
    while time.time() < deadline:
        for w in ua.GetRootControl().GetChildren():
            try:
                if 'ADWorkbench' in (w.Name or ''): tia_win = w; break
            except: pass
        if tia_win: break
        time.sleep(2)
    if not tia_win: log("V21 窗口未出现", "error"); return False
    tia_win.SetFocus(); time.sleep(3)

    # ── 切换到项目视图 ──
    gv = find_ctrl(tia_win, 'GoToProjectView')
    if gv:
        log("切换项目视图...", "step")
        gv.Click()
        time.sleep(8)
        # 重新获取窗口引用（视图切换可能改变控件树）
        tia_win = None
        for w in ua.GetRootControl().GetChildren():
            try:
                if 'ADWorkbench' in (w.Name or ''): tia_win = w; break
            except: pass
        if tia_win: tia_win.SetFocus(); time.sleep(3)
    else:
        log("已在项目视图", "info")

    if not tia_win:
        log("V21 窗口丢失", "error"); return False

    # ── 在项目树中点击 PLC 程序块（使按钮变可用！）──
    # 先找设备树
    log("在项目树中查找 PLC 程序块...", "step")
    tree_frame = find_ctrl(tia_win, 'ProjectNavigatorViewFrame')
    if not tree_frame:
        tree_frame = find_ctrl(tia_win, 'HardwareNavigationFrame')
    
    if tree_frame:
        # 找 "PLC_1" 或 "程序块" / "Program blocks" 节点并展开点击
        # 先点 PLC_1 设备
        plc_node = find_ctrl_multi(tree_frame, ['PLC_1', '[PLC]'])
        if plc_node:
            plc_node.Click()
            log(f"已点击 PLC 节点", "ok"); time.sleep(2)
            # 然后找程序块 → OB1
            ob1_node = find_ctrl_multi(tree_frame, ['Main [OB1]', 'OB1', 'Main'])
            if ob1_node:
                ob1_node.Click()
                log("已选中 Main [OB1] — 按钮应已激活", "ok")
                time.sleep(2)
            else:
                # 尝试双击展开
                try: plc_node.DoubleClick(); time.sleep(3); log("展开 PLC 节点", "info")
                except: pass
                ob1_node = find_ctrl_multi(tree_frame, ['Main [OB1]', 'OB1', 'Main'])
                if ob1_node:
                    ob1_node.Click(); log("已选中 OB1", "ok"); time.sleep(2)
                else:
                    log("未找到 OB1，尝试找其他程序块", "warn")
        else:
            log("未找到 PLC_1 节点", "warn")
    else:
        log("未找到项目树框架", "warn")

    # ── 直接点击"下载"（不需要启动仿真！PLCSIM 已处于 STOP 黄色待下载状态）──
    log("查找下载按钮...", "step")
    dl_btn = find_ctrl(tia_win, 'Download_ICO_PE')
    if dl_btn:
        dl_btn.Click()
        log("已点击下载", "ok")
        time.sleep(3)
    else:
        log("下载按钮不可用（未选中程序块）", "error")
        # 试试找其他下载控件
        dl_alt = find_ctrl(tia_win, 'LoadToTargetSystem')
        if dl_alt:
            dl_alt.Click(); log("已点击下载(alt)", "ok"); time.sleep(3)
        else:
            return False

    # ── 处理下载向导 ──
    log("处理下载向导对话框...", "step")
    deadline = time.time() + 120
    done = False
    while time.time() < deadline:
        for w in ua.GetRootControl().GetChildren():
            try:
                if not w.IsNativeWindow: continue
                wn = w.Name or ''
                # 找更多按钮文本
                for bt in ['下载(D)','下载','确定','OK','是','Yes','继续','完成','Finish','全部下载']:
                    try:
                        btn = w.ButtonControl(searchDepth=3, Name=bt)
                        if btn.Exists():
                            btn.Click(); time.sleep(0.5)
                            if bt in ('完成','Finish'): done = True
                            break
                    except: pass
                if done: break
            except: pass
        if done: break
        time.sleep(1)

    if done:
        log("下载完成！", "ok")
        proj.Save()
        try:
            from plcsim_api import archive_instance
            archive_instance('factoryio', GOLDEN_ZIP, STORAGE_PATH)
            log("Golden backup 已更新", "📦")
        except: pass
        return True
    else:
        log("下载向导未完成（检查 V21 窗口）", "warn")
        return False


# ═══════════════════════════════════════
#  步骤 3: Factory I/O
# ═══════════════════════════════════════
def step3_fio():
    sep("步骤 3: Factory I/O")
    if not os.path.exists(FIO_EXE): return True
    cfg_text = """# Factory I/O auto config — generated by p3_flow.py
ui.show_welcome_window = False
scene.start_in_run_mode = True
drivers.siemens_s7plcsim.auto_connect = True
drivers.siemens_s7plcsim.instance_name = 'factoryio'
drivers.siemens_s7plcsim.connection_timeout = 60
"""
    for p in [r'C:\ProgramData\Real Games\Factory IO\auto.cfg',
              os.path.join(os.path.expanduser('~'),'Documents','Factory IO','auto.cfg')]:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p,'w',encoding='utf-8-sig') as f: f.write(cfg_text)
    log("auto.cfg 已写入", "ok")
    subprocess.Popen([FIO_EXE], shell=True)
    log("Factory I/O 已启动", "ok")
    return True


# ═══════════════════════════════════════
#  Main
# ═══════════════════════════════════════
def main():
    print(f"\n{'='*56}\n  P3 端到端闭环\n{'='*56}\n")
    only_download = '--download-only' in sys.argv
    r = {}
    r['plcsim'] = step1_plcsim()
    if not r['plcsim']: sys.exit(1)
    r['download'] = step2_download()
    if not only_download and r['download']:
        r['fio'] = step3_fio()
    print(f"\n{BLUE}{'='*56}{RESET}")
    all_ok = all(r.values())
    for n, ok in r.items(): log(f"{n}: {'✅' if ok else '❌'}")
    print(f"\n{GREEN}P3 完成{')' if all_ok else ' 部分失败'}{RESET}")
    return 0 if all_ok else 1

if __name__ == '__main__':
    try: sys.exit(main())
    except KeyboardInterrupt: print("\n⚠ 中断"); sys.exit(1)
