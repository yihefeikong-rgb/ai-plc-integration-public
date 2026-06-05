"""
TIA Portal GUI 自动化下载模块。

通过 uiautomation 模拟 TIA Portal GUI 中的"下载到设备"操作，
绕过 Openness API 中 DownloadProvider 返回 null 的限制。

使用方法：
  python dl_plcsim_gui.py <project_name>

架构说明：
  - 本文件作为 独立子进程 运行（避免 uiautomation COM/STA 与 pythonnet/MTA 冲突）
  - 输出 JSON 到 stdout，调用方解析结果

流程:
  1. 找 TIA Portal 窗口（ADWorkbench 壳）
  2. 切到项目视图（Project View）
  3. 点工具栏"下载到设备"按钮
  4. 处理下载向导对话框

依赖:
  pip install uiautomation
"""
import sys
import json
import time
import os
import traceback

try:
    import uiautomation as ua
except ImportError:
    print(json.dumps({"success": False, "error": "uiautomation not installed. Run: pip install uiautomation"}))
    sys.exit(1)


def find_tia_window(timeout: float = 60.0) -> ua.Control:
    """在桌面上找到 TIA Portal 的窗口（ADWorkbench 壳）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for w in ua.GetRootControl().GetChildren():
            try:
                if "ADWorkbench" in (w.Name or ""):
                    return w
                if "Portal" in (w.Name or ""):
                    return w
            except Exception:
                continue
        time.sleep(1)
    raise TimeoutError(f"未找到 TIA Portal 窗口（{timeout}s 内）")


def switch_to_project_view(tia_window: ua.Control, timeout: float = 15.0) -> bool:
    """切换到项目视图。如果已在项目视图则直接返回。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        # 检查是否已在项目视图
        try:
            hw = tia_window.Control(searchDepth=6, automationId='HardwareNavigationFrame')
            if hw:
                return True
        except Exception:
            pass
        # 点 GoToProjectView 按钮
        try:
            def _find(ctrl):
                if 'GoToProjectView' in (ctrl.Name or ''):
                    ctrl.Click()
                    return True
                for child in ctrl.GetChildren():
                    if _find(child): return True
                return False
            _find(tia_window)
            time.sleep(3)
        except Exception:
            pass
        time.sleep(1)
    return False


def click_download_toolbar_button(tia_window: ua.Control) -> bool:
    """点工具栏上的下载到设备按钮。

    按钮 Name 特征: "Download" + "LoadToTarget"
    """
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            def _find(ctrl):
                try:
                    name = ctrl.Name or ""
                    if "Download" in name and "LoadToTarget" in name:
                        ctrl.Click()
                        return True
                except Exception:
                    pass
                for child in ctrl.GetChildren():
                    if _find(child): return True
                return False
            if _find(tia_window):
                time.sleep(2)
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def click_wizard_button(wizard_name: str, button_text: str, timeout: float = 15.0) -> bool:
    """在下载向导对话框中找到并点击指定按钮。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for w in ua.GetRootControl().GetChildren():
            try:
                w_name = w.Name or ""
                if wizard_name.lower() in w_name.lower() and w.IsNativeWindow:
                    for btn in w.GetChildren():
                        try:
                            if button_text.lower() in (btn.Name or "").lower():
                                btn.Click()
                                time.sleep(0.5)
                                return True
                        except Exception:
                            continue
            except Exception:
                continue
        time.sleep(0.5)
    return False


def handle_download_wizard(plcsim_interface: str = "",
                           timeout: float = 180.0) -> bool:
    """处理下载向导的完整流程。"""
    deadline = time.time() + timeout
    step = 0
    while time.time() < deadline and step < 30:
        step += 1
        time.sleep(1)
        for w in ua.GetRootControl().GetChildren():
            try:
                w_name = w.Name or ""
                if not w.IsNativeWindow:
                    continue

                # 扩展下载对话框
                if "Extended download" in w_name or "加载" in w_name:
                    if plcsim_interface:
                        try:
                            combo = w.ComboBoxControl(searchDepth=4)
                            if combo:
                                combo.Select(plcsim_interface)
                                time.sleep(0.5)
                        except Exception:
                            pass
                    for txt in ["Start search", "开始搜索", "Load", "下载"]:
                        if click_wizard_button(w_name, txt, timeout=3):
                            time.sleep(5)
                            break
                    continue

                # 确认对话框
                if any(k in w_name for k in ["Do you want", "confirm", "确认", "是否"]):
                    for txt in ["Yes", "是", "OK"]:
                        click_wizard_button(w_name, txt, timeout=3)
                    time.sleep(2)
                    continue

                # 编译/下载进度
                if any(k in w_name for k in ["Compile", "编译", "Download", "下载"]):
                    time.sleep(3)
                    continue

                # 完成
                if any(k in w_name for k in ["result", "结果", "completed", "完成"]):
                    for txt in ["Finish", "完成"]:
                        click_wizard_button(w_name, txt, timeout=3)
                    time.sleep(1)
                    return True

                # 错误
                if any(k in w_name for k in ["Error", "错误", "Failed", "失败"]):
                    try:
                        close_btn = w.ButtonControl(searchDepth=2)
                        if close_btn and "Close" in (close_btn.Name or ""):
                            close_btn.Click()
                    except Exception:
                        pass
                    return False
            except Exception:
                continue
    return False


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "success": False,
            "error": "Usage: python dl_plcsim_gui.py <project_name> [--device NAME] [--timeout N] [--interface NAME]"
        }))
        return 1

    project_name = sys.argv[1]
    timeout = 180
    pgpc_interface = ""

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--timeout" and i + 1 < len(sys.argv):
            timeout = int(sys.argv[i + 1])
            i += 2
        elif arg == "--interface" and i + 1 < len(sys.argv):
            pgpc_interface = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    try:
        # 1. 找 TIA Portal 窗口
        tia_win = find_tia_window(timeout=min(timeout, 30))
        tia_win.SetFocus()
        time.sleep(2)

        # 2. 切到项目视图
        if not switch_to_project_view(tia_win, timeout=15):
            print(json.dumps({
                "success": False,
                "error": "切换到项目视图失败",
            }))
            return 1

        # 3. 点下载按钮
        if not click_download_toolbar_button(tia_win):
            print(json.dumps({
                "success": False,
                "error": "未找到下载到设备按钮",
            }))
            return 1

        # 4. 处理向导
        success = handle_download_wizard(
            plcsim_interface=pgpc_interface,
            timeout=timeout,
        )

        result = {
            "success": success,
            "message": "下载到 PLCSIM 完成" if success else "下载向导未完成",
            "project": project_name,
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0 if success else 1

    except TimeoutError as e:
        print(json.dumps({"success": False, "error": f"Timeout: {e}"}))
        return 1
    except Exception as e:
        tb = traceback.format_exc()
        print(json.dumps({"success": False, "error": f"{type(e).__name__}: {e}", "traceback": tb}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
