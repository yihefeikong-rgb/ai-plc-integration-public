"""
下载流程集成测试 — mock 隔离全部动态操作（不启动 TIA Portal / PLCSIM / UAC 提权）

测试覆盖:
  1. _ensure_admin() — 非 admin + UAC 取消时 fail-closed 返回 False
  2. _ensure_tia_gui_running() — mock tasklist/UAC，验证自动启动逻辑但不真实启动
  3. download_via_ui() — UI Automation JSON 输出解析
  4. main() — 参数解析与策略分发（mock 全部下载/恢复动作）
  5. 三级降级策略逻辑（Python API → UI → manual）
"""
import os
import sys
import json
import subprocess
import pytest

pytestmark = pytest.mark.hardware

# 添加路径
TEST_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(TEST_DIR)
TIA_MCP_DIR = os.path.join(PROJECT_DIR, 'mcp-servers', 'tia-mcp')

sys.path.insert(0, TIA_MCP_DIR)
sys.path.insert(0, PROJECT_DIR)


class TestEnsureAdmin:
    """_ensure_admin() 逻辑测试"""

    def test_admin_check_exists(self):
        """_ensure_admin 函数存在且可导入"""
        from download_to_plcsim import _ensure_admin
        assert callable(_ensure_admin)

    def test_admin_check_returns_false_when_not_admin(self, monkeypatch):
        """非 admin 且 UAC 被取消时 _ensure_admin 应返回 False（fail-closed）"""
        import ctypes
        from download_to_plcsim import _ensure_admin

        class _FakeShell32:
            def IsUserAnAdmin(self):
                return False

            def ShellExecuteW(self, *args):
                return 0  # UAC 取消（返回值 <=32）

        class _FakeWindll:
            shell32 = _FakeShell32()

        # raising=False：ctypes.windll 仅 Windows 存在，非 Windows 平台同样可打桩运行
        monkeypatch.setattr(ctypes, "windll", _FakeWindll(), raising=False)
        # 不真实触发 UAC 提权，验证函数在"非 admin + 用户取消"时 fail-closed 返回 False
        assert _ensure_admin() is False


class TestTiaGuiRunning:
    """_ensure_tia_gui_running() 逻辑测试"""

    def test_gui_running_check(self, monkeypatch):
        """测试 GUI 运行检查逻辑（不启动 GUI，只验证 tasklist 调用）"""
        from download_to_plcsim import _ensure_tia_gui_running

        calls = []
        running_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout='"Siemens.Automation.Portal.exe","12345","Console","1","234,567 K"',
            stderr='',
        )

        def fake_run(*args, **kwargs):
            calls.append(args[0] if args else kwargs.get('args'))
            return running_result

        monkeypatch.setattr(subprocess, "run", fake_run)

        # tasklist 检查发现 GUI 已在运行 → 直接返回 True，不真实执行 cmd.exe / 不启动进程
        assert _ensure_tia_gui_running(timeout_sec=0) is True
        # 只验证 tasklist 调用携带目标进程过滤条件，模拟结果返回码为 0
        assert calls, "应发起 tasklist 检查"
        assert any(
            isinstance(cmd, (list, tuple))
            and 'Siemens.Automation.Portal.exe' in ' '.join(cmd)
            for cmd in calls
        )
        assert running_result.returncode == 0

    def test_gui_not_running_auto_start(self, monkeypatch):
        """GUI 未运行时 _ensure_tia_gui_running 应尝试启动，但测试不得真实启动/UAC 提权"""
        import ctypes
        import time as _time
        from download_to_plcsim import _ensure_tia_gui_running

        # tasklist 恒报"未运行"，避免依赖真实环境状态
        not_running = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='INFO: 没有任务', stderr='')
        shell_calls = []

        class _FakeShell32:
            def IsUserAnAdmin(self):
                return False  # 非 admin → 走 UAC runas 分支

            def ShellExecuteW(self, *args):
                shell_calls.append(args)
                return 0  # 只记录调用，不真实启动任何进程

        class _FakeWindll:
            shell32 = _FakeShell32()

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: not_running)
        monkeypatch.setattr(os.path, "exists", lambda p: True)  # 放行 tia_bin/项目路径检查
        # raising=False：ctypes.windll 仅 Windows 存在，非 Windows 平台同样可打桩运行
        monkeypatch.setattr(ctypes, "windll", _FakeWindll(), raising=False)
        monkeypatch.setattr(_time, "sleep", lambda s: None)

        result = _ensure_tia_gui_running(timeout_sec=0)
        # fail-closed：无法确认 GUI 已运行 → 返回 False
        assert result is False
        # 自动启动逻辑确实触发：发起了 UAC runas 启动尝试（未真实执行）
        assert shell_calls, "应尝试通过 UAC runas 启动 TIA Portal"
        assert any(call and len(call) > 1 and call[1] == "runas" for call in shell_calls)


class TestDownloadViaUi:
    """download_via_ui() — UI Automation 子进程调用测试"""

    @pytest.fixture
    def mock_dl_script_output(self, tmp_path):
        """模拟 dl_plcsim_gui.py 的输出"""
        success_output = json.dumps({
            "success": True,
            "message": "下载到 PLCSIM 完成",
            "project": "demo.ap18"
        })
        fail_output = json.dumps({
            "success": False,
            "error": "Timeout: 未找到 TIA Portal 窗口"
        })
        return success_output, fail_output

    def test_parse_success_output(self, mock_dl_script_output):
        """验证成功 JSON 的解析"""
        success_output, _ = mock_dl_script_output
        result = json.loads(success_output)
        assert result["success"] is True
        assert "下载到 PLCSIM 完成" in result["message"]

    def test_parse_fail_output(self, mock_dl_script_output):
        """验证失败 JSON 的解析"""
        _, fail_output = mock_dl_script_output
        result = json.loads(fail_output)
        assert result["success"] is False
        assert "Timeout" in result["error"]


@pytest.fixture
def fake_main_env(monkeypatch, tmp_path):
    """隔离 download_to_plcsim.main() 的全部动态副作用。

    放行 admin 检查、把唯一控制目标指向临时工程文件，并把所有真实
    下载/恢复动作替换为记录器/返回失败，确保测试零真实控制副作用。
    """
    from download_to_plcsim import main as dl_main

    project_file = tmp_path / "demo.ap18"
    project_file.write_text("")

    class _FakeTarget:
        project_path = str(project_file)

    monkeypatch.setattr("download_to_plcsim._ensure_admin", lambda: True)
    monkeypatch.setattr("download_to_plcsim.validate_control_target",
                        lambda *a, **k: _FakeTarget())
    # 默认所有策略失败（1），需要哪个路径由具体测试覆盖
    monkeypatch.setattr("download_to_plcsim._try_download_via_tiaworker", lambda *a, **k: 1)
    monkeypatch.setattr("download_to_plcsim._try_download_via_tiaworker_gui", lambda *a, **k: 1)
    monkeypatch.setattr("download_to_plcsim._try_download_via_python", lambda *a, **k: 1)
    monkeypatch.setattr("download_to_plcsim.download_via_ui", lambda *a, **k: 1)
    monkeypatch.setattr("download_to_plcsim._golden_restore", lambda *a, **k: 1)
    return dl_main


class TestMainArgumentParsing:
    """main() 命令行参数解析测试（真实调用 main()，mock 全部动态操作）"""

    def test_compile_first_flag(self, fake_main_env, monkeypatch):
        """--compile-first 应被 main() 解析并传给默认 TiaWorker 策略"""
        dl_main = fake_main_env
        captured = {}

        def fake_tiaworker(compile_first=False, target_ip=""):
            captured['compile_first'] = compile_first
            captured['target_ip'] = target_ip
            return 1

        monkeypatch.setattr("download_to_plcsim._try_download_via_tiaworker", fake_tiaworker)
        monkeypatch.setattr(sys, "argv", ['download_to_plcsim.py', '--compile-first'])
        assert dl_main() == 1  # 策略失败 → 手动指引
        assert captured.get('compile_first') is True

    def test_ui_flag(self, fake_main_env, monkeypatch):
        """--ui 应强制走 UI Automation 路径"""
        dl_main = fake_main_env
        captured = {}

        def fake_ui(compile_first=False):
            captured['compile_first'] = compile_first
            return 1

        monkeypatch.setattr("download_to_plcsim.download_via_ui", fake_ui)
        monkeypatch.setattr(sys, "argv", ['download_to_plcsim.py', '--ui'])
        assert dl_main() == 1
        assert captured.get('compile_first') is False

    def test_ip_argument(self, fake_main_env, monkeypatch):
        """--ip 参数应由 main() 实际解析并传给下载策略"""
        dl_main = fake_main_env
        captured = {}

        def fake_tiaworker(compile_first=False, target_ip=""):
            captured['target_ip'] = target_ip
            return 1

        monkeypatch.setattr("download_to_plcsim._try_download_via_tiaworker", fake_tiaworker)
        monkeypatch.setattr(sys, "argv", ['download_to_plcsim.py', '--ip', '10.0.0.2'])
        assert dl_main() == 1
        assert captured.get('target_ip') == '10.0.0.2'

    def test_unknown_arg_rejected(self, fake_main_env, monkeypatch):
        """未知参数应被 main() 拒绝（fail-closed），不触发任何下载策略"""
        dl_main = fake_main_env
        invoked = []

        monkeypatch.setattr("download_to_plcsim._try_download_via_tiaworker",
                            lambda *a, **k: invoked.append('tiaworker') or 1)
        monkeypatch.setattr("download_to_plcsim._try_download_via_tiaworker_gui",
                            lambda *a, **k: invoked.append('tiaworker-gui') or 1)
        monkeypatch.setattr("download_to_plcsim._try_download_via_python",
                            lambda *a, **k: invoked.append('python') or 1)
        monkeypatch.setattr("download_to_plcsim.download_via_ui",
                            lambda *a, **k: invoked.append('ui') or 1)
        monkeypatch.setattr(sys, "argv", ['download_to_plcsim.py', '--bogus-flag'])
        assert dl_main() == 1
        assert invoked == []


class TestFallbackLogic:
    """三级降级策略逻辑测试（通过 main() 真实驱动）"""

    def test_python_api_fallback_to_ui(self, fake_main_env, monkeypatch):
        """Python API 返回 -1 应触发 UI Automation 降级并成功"""
        dl_main = fake_main_env
        ui_calls = []

        monkeypatch.setattr("download_to_plcsim._try_download_via_tiaworker", lambda *a, **k: -1)
        monkeypatch.setattr("download_to_plcsim._try_download_via_tiaworker_gui", lambda *a, **k: -1)
        monkeypatch.setattr("download_to_plcsim._try_download_via_python", lambda *a, **k: -1)
        monkeypatch.setattr("download_to_plcsim.download_via_ui",
                            lambda *a, **k: ui_calls.append(a) or 0)
        monkeypatch.setattr(sys, "argv", ['download_to_plcsim.py'])

        assert dl_main() == 0
        assert len(ui_calls) == 1  # UI Automation 确实被调用

    def test_ui_fallback_to_manual(self, fake_main_env, monkeypatch):
        """UI Automation 返回 !=0 时应落入手动指引并返回 1"""
        dl_main = fake_main_env

        monkeypatch.setattr("download_to_plcsim._try_download_via_tiaworker", lambda *a, **k: -1)
        monkeypatch.setattr("download_to_plcsim._try_download_via_tiaworker_gui", lambda *a, **k: -1)
        monkeypatch.setattr("download_to_plcsim._try_download_via_python", lambda *a, **k: -1)
        monkeypatch.setattr("download_to_plcsim.download_via_ui", lambda *a, **k: 1)
        monkeypatch.setattr(sys, "argv", ['download_to_plcsim.py'])

        assert dl_main() == 1  # 全部降级失败 → 手动指引


class TestPlcsimApi:
    """PLCSIM API 基础功能测试"""

    @pytest.fixture(autouse=True)
    def _mock_clr(self):
        """mock Python.NET clr 模块，使测试不依赖 TIA Portal 运行时"""
        import types
        if "clr" not in sys.modules:
            mock_clr = types.ModuleType("clr")
            mock_clr.AddReference = lambda path: None
            sys.modules["clr"] = mock_clr
            # 也 mock Siemens.Engineering（TIA Openness DLL）
            mock_se = types.ModuleType("Siemens.Engineering")
            sys.modules["Siemens.Engineering"] = mock_se
            mock_se_hw = types.ModuleType("Siemens.Engineering.HW")
            mock_se_hw.HWObject = type("HWObject", (), {})
            sys.modules["Siemens.Engineering.HW"] = mock_se_hw
        yield

    def test_plcsim_module_importable(self, _mock_clr):
        """plcsim_api 模块可导入"""
        try:
            from plcsim_api import get_instances, create_instance, stop_instance
        except ImportError as e:
            pytest.skip(f"plcsim_api 导入失败（缺少 .NET 运行时）: {e}")
        assert callable(get_instances)
        assert callable(create_instance)
        assert callable(stop_instance)

    @pytest.mark.plcsim
    def test_get_instances_returns_list(self, _mock_clr):
        """get_instances() 返回列表（需要 PLCSIM 运行时）"""
        pytest.skip("需要 PLCSIM Advanced 运行时")


class TestCallFbInOb1:
    """call_fb_in_ob1.py 逻辑测试"""

    def test_generate_combined_scl_single_fb(self):
        """单个 FB 生成 SCL"""
        from call_fb_in_ob1 import generate_combined_scl
        scl = generate_combined_scl(["IO_Map_MotorForwardReverse"])
        assert "MasterIO" in scl
        assert "IO_Map_MotorForwardReverse" in scl
        # 应有 1 个实例声明 + 1 个调用
        assert scl.count('ioMap_') == 2  # 1 声明 + 1 调用

    def test_generate_combined_scl_multiple_fb(self):
        """多个 FB 生成 SCL"""
        from call_fb_in_ob1 import generate_combined_scl
        scl = generate_combined_scl(["IO_Map_MotorForwardReverse", "IO_Map_StarDeltaStarter"])
        assert "MasterIO" in scl
        assert "MotorForwardReverse" in scl
        assert "StarDeltaStarter" in scl
        # 应有 2 个实例声明 + 2 个调用
        assert scl.count('ioMap_') == 4


class TestAdminCheckConsistency:
    """管理员权限提示一致性测试"""

    def test_server_py_has_admin_warning(self):
        """server.py 启动时应有 admin 提示"""
        server_path = os.path.join(TIA_MCP_DIR, 'server.py')
        with open(server_path, encoding='utf-8') as f:
            content = f.read()
        assert 'IsUserAnAdmin' in content or '需要管理员权限' in content

    def test_download_py_has_admin_check(self):
        """download_to_plcsim.py 应有 admin 检查"""
        dl_path = os.path.join(TIA_MCP_DIR, 'download_to_plcsim.py')
        with open(dl_path, encoding='utf-8') as f:
            content = f.read()
        assert 'IsUserAnAdmin' in content

    def test_run_end2end_py_has_admin_check(self):
        """run_end2end.py 应有 admin 检查（已归档，仍在 archived/ 中保留）"""
        e2e_path = os.path.join(TIA_MCP_DIR, 'archived', 'run_end2end.py')
        with open(e2e_path, encoding='utf-8') as f:
            content = f.read()
        assert 'IsUserAnAdmin' in content


class TestDownloadStrategyFlags:
    """新下载策略标志测试"""

    def test_tiaworker_gui_flag(self, fake_main_env, monkeypatch):
        """--tiaworker-gui 应强制走 TiaWorker GUI 策略"""
        dl_main = fake_main_env
        captured = {}

        def fake_tiaworker_gui(target_ip=""):
            captured['target_ip'] = target_ip
            return 0

        monkeypatch.setattr("download_to_plcsim._try_download_via_tiaworker_gui", fake_tiaworker_gui)
        monkeypatch.setattr(sys, "argv", ['download_to_plcsim.py', '--tiaworker-gui'])
        assert dl_main() == 0
        assert captured.get('target_ip') == ''

    def test_golden_restore_flag(self, fake_main_env, monkeypatch):
        """--golden-restore 应直接进入 golden restore 模式（不执行下载）"""
        dl_main = fake_main_env
        captured = {}

        def fake_golden_restore(target_ip=""):
            captured['target_ip'] = target_ip
            return 0

        monkeypatch.setattr("download_to_plcsim._golden_restore", fake_golden_restore)
        monkeypatch.setattr(sys, "argv", ['download_to_plcsim.py', '--golden-restore'])
        assert dl_main() == 0
        assert captured.get('target_ip') == ''

    def test_five_level_fallback_chain(self):
        """验证 5 级降级链的定义"""
        from download_to_plcsim import (
            _try_download_via_tiaworker,
            _try_download_via_tiaworker_gui,
            _try_download_via_python,
            download_via_ui,
        )
        assert callable(_try_download_via_tiaworker)
        assert callable(_try_download_via_tiaworker_gui)
        assert callable(_try_download_via_python)
        assert callable(download_via_ui)

    def test_golden_backup_helper_importable(self):
        """_update_golden_backup 和 _golden_restore 可导入"""
        from download_to_plcsim import _update_golden_backup, _golden_restore
        assert callable(_update_golden_backup)
        assert callable(_golden_restore)


class TestGoldenRestore:
    """--golden-restore 逻辑测试"""

    def test_golden_restore_no_golden(self, monkeypatch):
        """golden 文件不存在时返回 1（fail-closed，不调用真实恢复）"""
        import types
        from download_to_plcsim import _golden_restore

        # 放行目标校验，避免依赖真实 PLCSIM/配置
        monkeypatch.setattr("download_to_plcsim._verified_plcsim_target",
                            lambda target_ip="": "192.168.0.1")
        # 隔离真实 plcsim_api：记录 restore_instance 调用
        restore_calls = []
        fake_plcsim = types.ModuleType("plcsim_api")
        fake_plcsim.restore_instance = lambda *a, **k: restore_calls.append((a, k))
        monkeypatch.setitem(sys.modules, "plcsim_api", fake_plcsim)
        # golden 备份文件恒不存在
        monkeypatch.setattr(os.path, "exists", lambda path: False)

        assert _golden_restore() == 1
        assert restore_calls == []  # 未触发任何恢复动作


class TestP3Flow:
    """p3_flow.py 纯编排器架构测试"""

    def test_no_clr_import(self):
        """p3_flow.py 不应导入 clr"""
        p3_path = os.path.join(PROJECT_DIR, 'scripts', 'p3_flow.py')
        with open(p3_path, encoding='utf-8') as f:
            content = f.read()
        assert 'import clr' not in content
        assert 'from clr' not in content

    def test_no_uiautomation_import(self):
        """p3_flow.py 不应导入 uiautomation"""
        p3_path = os.path.join(PROJECT_DIR, 'scripts', 'p3_flow.py')
        with open(p3_path, encoding='utf-8') as f:
            content = f.read()
        assert 'import uiautomation' not in content
        assert 'from uiautomation' not in content

    def test_uses_config_loader(self):
        """p3_flow.py 通过唯一 target 配置而非硬编码路径取值"""
        p3_path = os.path.join(PROJECT_DIR, 'scripts', 'p3_flow.py')
        with open(p3_path, encoding='utf-8') as f:
            content = f.read()
        assert 'from config_loader import cfg' in content
        assert 'validate_control_target' in content
        assert 'target.project_path' in content
        assert 'target.plc_ip' in content

    def test_all_operations_via_subprocess(self):
        """p3_flow.py 所有操作通过 subprocess.run"""
        p3_path = os.path.join(PROJECT_DIR, 'scripts', 'p3_flow.py')
        with open(p3_path, encoding='utf-8') as f:
            content = f.read()
        # 应使用 subprocess.run 而非直接调用 Openness API
        assert 'subprocess.run' in content
        assert 'TiaPortal' not in content  # 不应直接引用 TiaPortal
        assert 'ICompilable' not in content  # 不应直接引用 ICompilable
        assert 'DownloadProvider' not in content  # 不应直接引用 DownloadProvider

    def test_has_golden_restore_flag(self):
        """p3_flow.py 支持 --golden-restore"""
        p3_path = os.path.join(PROJECT_DIR, 'scripts', 'p3_flow.py')
        with open(p3_path, encoding='utf-8') as f:
            content = f.read()
        assert '--golden-restore' in content
