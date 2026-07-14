"""
server.py MCP 工具单元测试 — mock TiaWorker.exe 子进程

覆盖 TS002 需求的 9 个 MCP 工具：
  list_devices, import_scl_file, create_plc_tags, compile_project,
  download_to_plcsim, generate_scl_code, generate_and_import,
  create_ladder_block, full_pipeline

注意：使用 autouse fixture 保存/恢复 sys.modules 以避免污染其他测试。
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, PropertyMock, ANY

import pytest

# ── 路径设置 ──
_PROJECT = Path(__file__).parent.parent
_TIA_MCP = _PROJECT / "mcp-servers" / "tia-mcp"
_SAFETY = _PROJECT / "safety"
sys.path.insert(0, str(_TIA_MCP))
sys.path.insert(0, str(_SAFETY))
sys.path.insert(0, str(_PROJECT))


# ── 辅助函数 ──
def _mock_subprocess_run(stdout_json: dict, returncode: int = 0,
                          stderr: str = "") -> MagicMock:
    """创建模拟的 subprocess.run 返回值"""
    mock = MagicMock()
    mock.returncode = returncode
    mock.stdout = json.dumps(stdout_json) if stdout_json else ""
    mock.stderr = stderr
    return mock


def _patch_worker(server_module, response: dict, returncode: int = 0):
    """装饰器：mock _run_worker 返回指定响应"""
    return patch.object(
        server_module, "_run_worker",
        return_value=response,
    )


# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def server():
    """返回 mock 好的 server 模块"""
    # 保存将被修改的模块
    _saved = {}
    _keys_to_mock = [
        "clr", "Siemens", "Siemens.Engineering", "System", "System.IO",
        "safety", "safety.validator", "audit", "ladder_renderer",
        "create_plc_tags", "download_to_plcsim", "tia_session",
        "gen_io_map", "call_fb_in_ob1", "config_loader",
    ]
    for key in _keys_to_mock:
        _saved[key] = sys.modules.get(key)

    # Mock Windows 特有模块
    sys.modules["clr"] = MagicMock()
    sys.modules["Siemens"] = MagicMock()
    sys.modules["Siemens.Engineering"] = MagicMock()
    sys.modules["System"] = MagicMock()
    sys.modules["System.IO"] = MagicMock()

    # Mock 安全模块
    _mock_validator = MagicMock()
    _mock_validator.validate.return_value = MagicMock(allowed=True, reason="")
    sys.modules["safety.validator"] = MagicMock(validator=_mock_validator)
    sys.modules["safety"] = sys.modules["safety.validator"]

    # Mock audit
    sys.modules["audit"] = MagicMock()
    sys.modules["audit"].audit_log = MagicMock()

    # Mock ladder_renderer
    sys.modules["ladder_renderer"] = MagicMock()

    # Mock create_plc_tags
    _mock_cpt = MagicMock()
    _mock_cpt.create_tags = MagicMock(
        return_value={"status": "ok", "created": 2, "skipped": 0, "errors": []}
    )
    sys.modules["create_plc_tags"] = _mock_cpt

    # Mock download_to_plcsim
    _mock_dl = MagicMock()
    _mock_dl._try_download_via_python = MagicMock(return_value=0)
    _mock_dl._try_download_via_tiaworker = MagicMock(return_value=0)
    _mock_dl._try_download_via_tiaworker_gui = MagicMock(return_value=-1)
    _mock_dl.download_via_ui = MagicMock(return_value=0)
    sys.modules["download_to_plcsim"] = _mock_dl

    # Mock tia_session
    sys.modules["tia_session"] = MagicMock()

    # Mock gen_io_map
    _mock_gen = MagicMock()
    _mock_gen.generate_io_map = MagicMock(return_value="FUNCTION_BLOCK ...")
    sys.modules["gen_io_map"] = _mock_gen

    # Mock call_fb_in_ob1
    _mock_call = MagicMock()
    _mock_call.insert_fb_calls = MagicMock(return_value=0)
    sys.modules["call_fb_in_ob1"] = _mock_call

    # Mock config_loader
    _mock_cfg = MagicMock()
    _mock_cfg.tia.project_path = "C:\\test\\project.ap21"
    _mock_cfg.tia.output_dir = "C:\\test\\output"
    _mock_cfg.deepseek.api_key = "sk-test-key"
    _mock_cfg.deepseek.api_url = "https://api.deepseek.com/v1/chat/completions"
    _mock_cfg.deepseek.model = "deepseek-chat"
    _mock_cfg.deepseek.temperature = 0.3
    _mock_cfg.deepseek.max_tokens = 4096
    _mock_cfg.deepseek.timeout_sec = 60
    _mock_cfg.generation.templates_dir = "C:\\test\\templates"
    _target = SimpleNamespace(
        tia_version="V21",
        project_path=Path("C:\\test\\project.ap21"),
        plc_ip="192.168.0.110",
        plcsim_instance="factoryio",
    )
    _mock_cfg.target = _target
    sys.modules["config_loader"] = MagicMock()
    sys.modules["config_loader"].cfg = _mock_cfg
    sys.modules["config_loader"].validate_control_target = MagicMock(return_value=_target)
    sys.modules["config_loader"].validate_ladder_spec = MagicMock(return_value={"valid": True})
    sys.modules["config_loader"].safety_validate_ladder = MagicMock(return_value={"safe": True})

    # 删除可能缓存的 server 模块
    for mod_name in list(sys.modules.keys()):
        if mod_name == "server" or mod_name.startswith("server."):
            del sys.modules[mod_name]

    import server as tia_server
    # 绝大多数工具测试只覆盖工具契约；认证门由 TestAuth 单独恢复真实实现验证。
    tia_server._real_require_auth_for_test = tia_server._require_auth
    tia_server._require_auth = MagicMock()

    yield tia_server

    # 清理：恢复/删除 mock 模块
    for key in _keys_to_mock:
        if _saved.get(key) is not None:
            sys.modules[key] = _saved[key]
        elif key in sys.modules:
            del sys.modules[key]
    # 删除 server 模块缓存
    for mod_name in list(sys.modules.keys()):
        if mod_name == "server" or mod_name.startswith("server."):
            del sys.modules[mod_name]


# ═══════════════════════════════════════════════════════════════
# 测试: _run_worker
# ═══════════════════════════════════════════════════════════════

class TestRunWorker:
    """测试 _run_worker 内部函数"""

    def test_returns_parsed_json_on_success(self, server):
        """正常返回 JSON 时正确解析"""
        expected = {"ok": True, "result": {"devices": []}, "error": None}
        with patch("subprocess.run") as mock_run, patch.object(Path, "exists", return_value=True):
            mock_run.return_value = _mock_subprocess_run(expected)
            with patch("os.unlink"):
                result = server._run_worker(
                    "list-devices", {"ProjectPath": "C:\\test\\project.ap21"}
                )
        assert result == expected

    def test_returns_error_on_missing_exe(self, server):
        """TiaWorker.exe 不存在时返回错误"""
        with patch.object(Path, "exists", return_value=False):
            result = server._run_worker("list-devices", {})
        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_returns_error_on_timeout(self, server):
        """超时时返回错误"""
        import subprocess as sp
        with patch("subprocess.run") as mock_run, patch.object(Path, "exists", return_value=True):
            mock_run.side_effect = sp.TimeoutExpired(cmd="test", timeout=120)
            with patch("os.unlink"):
                result = server._run_worker("compile", {})
        assert result["status"] == "error"
        assert "timeout" in result["error"]

    def test_returns_error_on_invalid_json(self, server):
        """TiaWorker 返回非 JSON 时返回错误"""
        with patch("subprocess.run") as mock_run, patch.object(Path, "exists", return_value=True):
            mock = MagicMock()
            mock.stdout = "Not JSON output"
            mock.stderr = ""
            mock_run.return_value = mock
            with patch("os.unlink"):
                result = server._run_worker("compile", {})
        assert result["status"] == "error"
        assert "Invalid JSON" in result["error"]

    def test_forces_configured_v21_and_rejects_a_nonzero_worker_result(self, server):
        worker_result = {"ok": True, "result": {"success": False}, "error": None}
        with patch("subprocess.run") as mock_run, patch.object(Path, "exists", return_value=True):
            mock_run.return_value = _mock_subprocess_run(worker_result, returncode=1)
            with patch("os.unlink"):
                result = server._run_worker("compile", {"ProjectPath": "C:\\test\\project.ap21"})

        command = mock_run.call_args.args[0]
        assert command[1] == "--tia-major-version=V21"
        assert result["status"] == "error"
        assert result["ok"] is False

    def test_resolve_path_rejects_a_project_outside_the_single_target(self, server):
        with pytest.raises(ValueError, match="唯一配置"):
            server._resolve_path("C:\\other\\project.ap21")


# ═══════════════════════════════════════════════════════════════
# 测试: list_devices
# ═══════════════════════════════════════════════════════════════

class TestListDevices:
    """测试 list_devices MCP 工具"""

    def test_returns_devices(self, server):
        mock_response = {
            "ok": True,
            "result": {"devices": [{"name": "PLC_1", "type": "S7-1200"}]},
            "error": None,
        }
        with _patch_worker(server, mock_response):
            result = server.list_devices(project_path="C:\\test\\project.ap21")
        assert result["ok"] is True
        assert result["result"]["devices"][0]["name"] == "PLC_1"

    def test_no_project_path_uses_default(self, server):
        mock_response = {"ok": True, "result": {"devices": []}, "error": None}
        with _patch_worker(server, mock_response):
            result = server.list_devices()
        assert result["ok"] is True

    def test_returns_error_when_worker_fails(self, server):
        mock_response = {"ok": False, "result": None, "error": "No project"}
        with _patch_worker(server, mock_response):
            result = server.list_devices(project_path="C:\\test\\project.ap21")
        assert result["ok"] is False
        assert result["error"] == "No project"


# ═══════════════════════════════════════════════════════════════
# 测试: import_scl_file
# ═══════════════════════════════════════════════════════════════

class TestImportSclFile:
    """测试 import_scl_file MCP 工具"""

    def test_imports_scl_successfully(self, server):
        mock_response = {
            "ok": True,
            "result": {
                "fileName": "MotorControl.scl",
                "generated": 1,
                "blocks": ["MotorControl"],
            },
            "error": None,
        }
        with _patch_worker(server, mock_response):
            result = server.import_scl_file(
                scl_code="FUNCTION_BLOCK MotorControl ...",
                block_name="MotorControl",
                project_path="C:\\test\\project.ap21",
            )
        assert result["ok"] is True
        assert result["result"]["blocks"] == ["MotorControl"]

    def test_import_uses_cleaned_non_user_controlled_temp_path(self, server):
        captured = {}

        def fake_worker(_command, payload):
            captured["path"] = Path(payload["SclFilePath"])
            assert captured["path"].exists()
            return {"status": "ok"}

        with patch.object(server, "_run_worker", side_effect=fake_worker):
            result = server.import_scl_file(
                scl_code="FUNCTION_BLOCK SafeBlock END_FUNCTION_BLOCK",
                block_name="..\\not-a-path",
                project_path="C:\\test\\project.ap21",
            )

        assert result["status"] == "ok"
        assert captured["path"].name.startswith("tia-scl-")
        assert not captured["path"].exists()

    def test_imports_scl_with_tags(self, server):
        mock_response = {
            "ok": True,
            "result": {"fileName": "Test.scl", "generated": 1, "blocks": ["Test"]},
            "error": None,
        }
        with _patch_worker(server, mock_response):
            result = server.import_scl_file(
                scl_code="FUNCTION_BLOCK Test ...",
                block_name="Test",
                project_path="C:\\test\\project.ap21",
                tags='[{"name":"I0_0","dataType":"Bool","address":"%I0.0","comment":"test"}]',
            )
        assert result["ok"] is True

    def test_invalid_tags_json(self, server):
        result = server.import_scl_file(
            scl_code="FUNCTION_BLOCK Test ...",
            block_name="Test",
            project_path="C:\\test\\project.ap21",
            tags="not valid json",
        )
        assert result["status"] == "error"
        assert "JSON" in result["error"]

    def test_tag_creation_failure(self, server):
        sys.modules["create_plc_tags"].create_tags.return_value = {
            "status": "error",
            "error": "TIA API failed",
        }
        result = server.import_scl_file(
            scl_code="FUNCTION_BLOCK Test ...",
            block_name="Test",
            project_path="C:\\test\\project.ap21",
            tags='[{"name":"I0_0","dataType":"Bool","address":"%I0.0"}]',
        )
        assert result["status"] == "error"
        assert "标签创建失败" in result["error"]

    def test_lint_blocks_import_with_errors(self, server):
        """TS022 MEDIUM: lint 拦截时阻止导入 + 审计日志 + 不调用 worker"""
        # 确保 scl_lint 模块可导入（使用真实 scl_lint）
        bad_scl = """
FUNCTION "FC_LintBlocked" : Void
   VAR_INPUT
      Msg : String[80];
   END_VAR
BEGIN
END_FUNCTION
"""
        from unittest.mock import patch as upatch
        # Mock _run_worker 以验证它不会被调用
        mock_worker = MagicMock(return_value={"ok": True})
        with upatch.object(server, "_run_worker", mock_worker):
            result = server.import_scl_file(
                scl_code=bad_scl,
                block_name="LintBlocked",
                project_path="C:\\test\\project.ap21",
            )
        # 应该被 lint 拦截
        assert result["status"] == "error"
        assert "lint_errors" in result
        assert len(result["lint_errors"]) >= 1
        assert "违规" in result["message"]
        # _run_worker 不应被调用（lint 在写盘前拦截）
        mock_worker.assert_not_called()
        # audit_log 应被调用
        audit_mock = sys.modules["audit"].audit_log
        # 至少有一个调用包含 lint_blocked
        lint_blocked_calls = [
            c for c in audit_mock.call_args_list
            if c[1].get("result") == "lint_blocked"
        ]
        assert len(lint_blocked_calls) >= 1, "audit_log 应在 lint 拦截时被调用"


# ═══════════════════════════════════════════════════════════════
# 测试: create_plc_tags (MCP 工具)
# ═══════════════════════════════════════════════════════════════

class TestCreatePlcTagsTool:
    """测试 create_plc_tags MCP 工具"""

    def test_creates_tags_successfully(self, server):
        result = server.create_plc_tags(
            tags_json='[{"name":"I0_0","dataType":"Bool","address":"%I0.0","comment":"test"}]',
            project_path="C:\\test\\project.ap21",
        )
        assert result["status"] == "ok"
        assert result["created"] == 2

    def test_invalid_json_returns_error(self, server):
        result = server.create_plc_tags(
            tags_json="not json",
            project_path="C:\\test\\project.ap21",
        )
        assert result["status"] == "error"
        assert "解析失败" in result["error"]

    def test_no_project_path_uses_default(self, server):
        result = server.create_plc_tags(
            tags_json='[{"name":"I0_0","dataType":"Bool","address":"%I0.0"}]',
        )
        assert result["status"] == "ok"


# ═══════════════════════════════════════════════════════════════
# 测试: compile_project
# ═══════════════════════════════════════════════════════════════

class TestCompileProject:
    """测试 compile_project MCP 工具"""

    def test_compile_success(self, server):
        mock_response = {
            "ok": True,
            "result": {"success": True, "errors": 0, "warnings": 2},
            "error": None,
        }
        with _patch_worker(server, mock_response):
            result = server.compile_project(project_path="C:\\test\\project.ap21")
        assert result["ok"] is True
        assert result["result"]["success"] is True
        assert result["result"]["warnings"] == 2

    def test_compile_failure(self, server):
        mock_response = {
            "ok": True,
            "result": {"success": False, "errors": 3, "warnings": 1},
            "error": None,
        }
        with _patch_worker(server, mock_response):
            result = server.compile_project(project_path="C:\\test\\project.ap21")
        assert result["result"]["success"] is False
        assert result["result"]["errors"] == 3

    def test_compile_worker_error(self, server):
        mock_response = {"ok": False, "result": None, "error": "No PLC device"}
        with _patch_worker(server, mock_response):
            result = server.compile_project(project_path="C:\\test\\project.ap21")
        assert result["ok"] is False
        assert result["error"] == "No PLC device"


# ═══════════════════════════════════════════════════════════════
# 测试: download_to_plcsim
# ═══════════════════════════════════════════════════════════════

class TestDownloadToPlcsim:
    """测试 download_to_plcsim MCP 工具"""

    def test_auto_mode_success(self, server):
        result = server.download_to_plcsim(
            project_path="C:\\test\\project.ap21",
            method="auto",
        )
        assert result["status"] == "ok"

    def test_tiaworker_mode(self, server):
        result = server.download_to_plcsim(
            project_path="C:\\test\\project.ap21",
            method="tiaworker",
        )
        assert result["status"] == "ok"
        sys.modules["download_to_plcsim"]._try_download_via_tiaworker.assert_called_once()
        sys.modules["download_to_plcsim"]._try_download_via_python.assert_not_called()

    def test_ui_mode(self, server):
        result = server.download_to_plcsim(
            project_path="C:\\test\\project.ap21",
            method="ui",
        )
        assert result["status"] == "ok"

    def test_auto_fallback_to_ui(self, server):
        sys.modules["download_to_plcsim"]._try_download_via_tiaworker.return_value = -1
        sys.modules["download_to_plcsim"]._try_download_via_tiaworker_gui.return_value = -1
        sys.modules["download_to_plcsim"]._try_download_via_python.return_value = -1
        result = server.download_to_plcsim(
            project_path="C:\\test\\project.ap21",
            method="auto",
        )
        assert result["status"] == "ok"
        assert "UI Automation" in result["message"]

    def test_rejects_an_unknown_download_method(self, server):
        result = server.download_to_plcsim(
            project_path="C:\\test\\project.ap21",
            method="shell",
        )
        assert result["status"] == "error"
        assert "method" in result["error"]

    def test_compile_first_flag(self, server):
        result = server.download_to_plcsim(
            project_path="C:\\test\\project.ap21",
            compile_first=True,
            method="tiaworker",
        )
        assert result["status"] == "ok"


# ═══════════════════════════════════════════════════════════════
# 测试: generate_scl_code
# ═══════════════════════════════════════════════════════════════

class TestGenerateSclCode:
    """测试 generate_scl_code MCP 工具"""

    def test_generates_scl(self, server):
        mock_deepseek = {
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"scl_code": "FUNCTION_BLOCK Test ...", "block_name": "Test"}\n```'
                    }
                }
            ]
        }
        with patch.object(server, "_deepseek_chat", return_value=mock_deepseek):
            result = server.generate_scl_code(
                description="电机正反转控制",
                template="motor",
            )
        assert result["status"] == "ok"
        assert "scl_code" in result["data"]
        assert result["data"]["block_name"] == "Test"

    def test_generates_scl_no_code_block(self, server):
        mock_deepseek = {
            "choices": [
                {
                    "message": {
                        "content": '{"scl_code": "FUNCTION_BLOCK FB1 ...", "block_name": "FB1"}'
                    }
                }
            ]
        }
        with patch.object(server, "_deepseek_chat", return_value=mock_deepseek):
            result = server.generate_scl_code(
                description="简单控制",
                template="general",
            )
        assert result["status"] == "ok"
        assert result["data"]["block_name"] == "FB1"

    def test_api_error(self, server):
        with patch.object(server, "_deepseek_chat", side_effect=Exception("API down")):
            result = server.generate_scl_code(
                description="控制逻辑",
            )
        assert result["status"] == "error"
        assert "API down" in result["error"]


# ═══════════════════════════════════════════════════════════════
# 测试: generate_and_import
# ═══════════════════════════════════════════════════════════════

class TestGenerateAndImport:
    """测试 generate_and_import MCP 工具"""

    def test_generates_and_imports(self, server):
        mock_deepseek = {
            "choices": [
                {
                    "message": {
                        "content": '{"scl_code": "FUNCTION_BLOCK GenTest ...", "block_name": "GenTest"}'
                    }
                }
            ]
        }
        mock_worker = {
            "ok": True,
            "result": {"fileName": "GenTest.scl", "generated": 1, "blocks": ["GenTest"]},
            "error": None,
        }
        with patch.object(server, "_deepseek_chat", return_value=mock_deepseek):
            with _patch_worker(server, mock_worker):
                result = server.generate_and_import(
                    description="测试生成",
                    project_path="C:\\test\\project.ap21",
                )
        assert result["ok"] is True
        assert result["result"]["blocks"] == ["GenTest"]

    def test_generate_fails_returns_error(self, server):
        mock_deepseek = {
            "choices": [{"message": {"content": "I cannot generate this"}}]
        }
        with patch.object(server, "_deepseek_chat", return_value=mock_deepseek):
            result = server.generate_and_import(
                description="测试",
                project_path="C:\\test\\project.ap21",
            )
        assert result["status"] == "error"

    def test_empty_scl_code(self, server):
        mock_deepseek = {
            "choices": [
                {"message": {"content": '{"scl_code": "", "block_name": "Empty"}'}}
            ]
        }
        with patch.object(server, "_deepseek_chat", return_value=mock_deepseek):
            result = server.generate_and_import(
                description="测试",
                project_path="C:\\test\\project.ap21",
            )
        assert result["status"] == "error"
        assert "未生成有效" in result["error"]

    def test_custom_block_name(self, server):
        mock_deepseek = {
            "choices": [
                {
                    "message": {
                        "content": '{"scl_code": "FUNCTION_BLOCK Custom ...", "block_name": "AutoName"}'
                    }
                }
            ]
        }
        mock_worker = {
            "ok": True,
            "result": {"fileName": "MyBlock.scl", "generated": 1, "blocks": ["MyBlock"]},
            "error": None,
        }
        with patch.object(server, "_deepseek_chat", return_value=mock_deepseek):
            with _patch_worker(server, mock_worker):
                result = server.generate_and_import(
                    description="测试",
                    block_name="MyBlock",
                    project_path="C:\\test\\project.ap21",
                )
        assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════
# 测试: create_ladder_block
# ═══════════════════════════════════════════════════════════════

class TestCreateLadderBlock:
    """测试 create_ladder_block MCP 工具"""

    def test_cart3cycle_fast_path_is_fail_closed_until_audited(self, server):
        with patch("subprocess.run") as subprocess_run:
            result = server.create_ladder_block(
                description="cart3cycle",
                block_name="AutoCart3Cycle",
            )
        assert result["status"] == "error"
        assert "安全阻断" in result["error"]
        subprocess_run.assert_not_called()

    def test_semantic_failure_blocks_cartgen_and_tia_import(self, server):
        unsafe_spec = {"blockName": "UnsafeMotor", "networks": []}
        with patch.object(server, "_gen_lad_spec", return_value=unsafe_spec), \
             patch.object(server, "safety_validate_ladder", return_value={
                 "safe": False, "warnings": ["缺少常闭急停互锁 iStop"],
             }), \
             patch.object(server, "_run_cartgen") as run_cartgen, \
             patch.object(server, "_import_xml_into_tia") as import_tia:
            result = server.create_ladder_block(
                description="电机正反转",
                block_name="UnsafeMotor",
            )

        assert result["status"] == "error"
        assert "语义安全校验失败" in result["error"]
        run_cartgen.assert_not_called()
        import_tia.assert_not_called()

    def test_cartgen_artifacts_require_an_exact_io_mapping_manifest(self, server, tmp_path):
        spec = {
            "blockName": "MappedBlock",
            "interface": {
                "inputs": [{
                    "name": "iStart", "type": "Bool", "address": "%I0.0", "comment": "start",
                }],
                "outputs": [{
                    "name": "oRun", "type": "Bool", "address": "%Q0.0", "comment": "run",
                }],
            },
        }
        xml_path = tmp_path / "MappedBlock.xml"
        xml_path.write_text("<Document />", encoding="utf-8")

        with pytest.raises(RuntimeError, match="I/O 映射清单"):
            server._verify_cartgen_artifacts(spec, str(xml_path))

        manifest_path = tmp_path / "MappedBlock.io-map.json"
        manifest_path.write_text(json.dumps({
            "blockName": "MappedBlock",
            "inputs": [{"name": "iStart", "type": "Bool", "address": "%I0.0"}],
            "outputs": [{"name": "oRun", "type": "Bool", "address": "%Q0.0"}],
        }), encoding="utf-8")

        server._verify_cartgen_artifacts(spec, str(xml_path))


# ═══════════════════════════════════════════════════════════════
# 测试: _resolve_path
# ═══════════════════════════════════════════════════════════════

class TestResolvePath:
    """测试 _resolve_path 辅助函数"""

    def test_rejects_a_project_path_outside_the_configured_target(self, server):
        with pytest.raises(ValueError, match="唯一配置"):
            server._resolve_path("C:\\custom\\project.ap21")

    def test_uses_default_when_empty(self, server):
        result = server._resolve_path("")
        assert result == "C:\\test\\project.ap21"


# ═══════════════════════════════════════════════════════════════
# 测试: _check_auth / _require_auth
# ═══════════════════════════════════════════════════════════════

class TestAuth:
    """测试认证机制"""

    def test_check_auth_empty_token(self, server):
        server._AUTH_TOKEN = ""
        assert server._check_auth("") is False
        assert server._check_auth("anything") is False

    def test_check_auth_correct(self, server):
        server._AUTH_TOKEN = "secret123"
        assert server._check_auth("secret123") is True

    def test_check_auth_wrong(self, server):
        server._AUTH_TOKEN = "secret123"
        assert server._check_auth("wrong") is False

    def test_require_auth_passes(self, server):
        server._AUTH_TOKEN = "secret123"
        server._real_require_auth_for_test("secret123")

    def test_require_auth_fails(self, server):
        server._AUTH_TOKEN = "secret123"
        with pytest.raises(PermissionError, match="认证失败"):
            server._real_require_auth_for_test("wrong")

    def test_unconfigured_auth_blocks_tool_before_worker(self, server):
        server._AUTH_TOKEN = ""
        server._require_auth = server._real_require_auth_for_test
        with patch.object(server, "_run_worker") as worker:
            with pytest.raises(PermissionError, match="MCP_AUTH_TOKEN"):
                server.list_devices(project_path="C:\\test\\project.ap21")
            worker.assert_not_called()


# ═══════════════════════════════════════════════════════════════
# 测试: _safety_gate
# ═══════════════════════════════════════════════════════════════

class TestSafetyGate:
    """测试安全闸门"""

    def test_safety_gate_allows(self, server):
        result = server._safety_gate("import_scl_file", block_name="Test")
        assert result is None

    def test_safety_gate_blocks(self, server):
        # 重新设置 mock validator 返回拒绝
        sys.modules["safety.validator"].validator.validate.return_value = MagicMock(
            allowed=False, reason="断路器已熔断"
        )
        result = server._safety_gate("download_to_plcsim", block_name="Test")
        assert result is not None
        assert result["status"] == "error"
        assert "安全链拒绝" in result["message"]


# ═══════════════════════════════════════════════════════════════
# D-09: 数据契约 — generate_scl_code 返回顶层 scl_code/block_name
# ═══════════════════════════════════════════════════════════════

class TestGenerateSclCodeContract:
    """D-09: generate_scl_code 返回值包含顶层 scl_code 和 block_name"""

    def test_top_level_scl_code_and_block_name(self, server):
        mock_deepseek = {
            "choices": [
                {
                    "message": {
                        "content": '{"scl_code": "FUNCTION_BLOCK Motor...", "block_name": "Motor"}'
                    }
                }
            ]
        }
        with patch.object(server, "_deepseek_chat", return_value=mock_deepseek):
            result = server.generate_scl_code(description="电机控制")
        assert result["status"] == "ok"
        # 顶层字段
        assert result["scl_code"] == "FUNCTION_BLOCK Motor..."
        assert result["block_name"] == "Motor"
        # 向后兼容的 data 子字典
        assert result["data"]["scl_code"] == "FUNCTION_BLOCK Motor..."
        assert result["data"]["block_name"] == "Motor"

    def test_top_level_fallback_when_data_missing(self, server):
        """当 data 子字典为空时,顶层字段仍应有值"""
        mock_deepseek = {
            "choices": [
                {
                    "message": {
                        "content": '{"scl_code": "FUNCTION_BLOCK FB1...", "block_name": "FB1"}'
                    }
                }
            ]
        }
        with patch.object(server, "_deepseek_chat", return_value=mock_deepseek):
            result = server.generate_scl_code(description="测试")
        assert result["scl_code"] == "FUNCTION_BLOCK FB1..."
        assert result["block_name"] == "FB1"


# ═══════════════════════════════════════════════════════════════
# D-02: import_scl_file 的 replace 参数
# ═══════════════════════════════════════════════════════════════

class TestImportSclFileReplace:
    """D-02: import_scl_file 支持 replace 参数"""

    def test_default_replace_false_uses_import_scl(self, server):
        """replace=False(默认) 时调用 import-scl 命令"""
        with patch.object(server, "_run_worker", return_value={"ok": True}) as mock_worker:
            server.import_scl_file(
                scl_code="FUNCTION_BLOCK Test ...",
                block_name="Test",
                project_path="C:\\test\\project.ap21",
            )
        # 验证调用命令为 "import-scl"
        call_kwargs = mock_worker.call_args[0]
        assert call_kwargs[0] == "import-scl"

    def test_replace_true_uses_import_scl_replace(self, server):
        """replace=True 时调用 import-scl-replace 命令"""
        with patch.object(server, "_run_worker", return_value={"ok": True}) as mock_worker:
            server.import_scl_file(
                scl_code="FUNCTION_BLOCK Test ...",
                block_name="Test",
                project_path="C:\\test\\project.ap21",
                replace=True,
            )
        call_kwargs = mock_worker.call_args[0]
        assert call_kwargs[0] == "import-scl-replace"

    def test_replace_passes_same_payload(self, server):
        """replace=True/False 传入相同的 payload 结构"""
        with patch.object(server, "_run_worker", return_value={"ok": True}) as mock_worker:
            server.import_scl_file(
                scl_code="FUNCTION_BLOCK X ...",
                block_name="X",
                project_path="C:\\test\\project.ap21",
                replace=False,
            )
            _, payload_plain = mock_worker.call_args[0]
            assert "ProjectPath" in payload_plain
            assert "SclFilePath" in payload_plain

        with patch.object(server, "_run_worker", return_value={"ok": True}) as mock_worker:
            server.import_scl_file(
                scl_code="FUNCTION_BLOCK X ...",
                block_name="X",
                project_path="C:\\test\\project.ap21",
                replace=True,
            )
            _, payload_replace = mock_worker.call_args[0]
            assert "ProjectPath" in payload_replace
            assert "SclFilePath" in payload_replace


# ═══════════════════════════════════════════════════════════════
# D-03: BOM 防御
# ═══════════════════════════════════════════════════════════════

class TestBomDefense:
    """D-03: 写 .scl 文件前清除 BOM + UTF-8 无 BOM"""

    @staticmethod
    def _capture_temp_scl(server, scl_code: str) -> bytes:
        captured = {}

        def fake_worker(_command, payload):
            captured["content"] = Path(payload["SclFilePath"]).read_bytes()
            return {"ok": True}

        with patch.object(server, "_run_worker", side_effect=fake_worker):
            server.import_scl_file(
                scl_code=scl_code,
                block_name="Test",
                project_path="C:\\test\\project.ap21",
            )
        return captured["content"]

    def test_bom_stripped_before_write(self, server):
        """包含 BOM 的 scl_code 写入时 BOM 被清除"""
        bom_scl = "\ufeffFUNCTION_BLOCK Test ..."
        written = self._capture_temp_scl(server, bom_scl)
        assert written.startswith(b"FUNCTION_BLOCK")
        assert not written.startswith(b"\xef\xbb\xbf"), "BOM 未被清除"

    def test_no_bom_normal_code_unchanged(self, server):
        """不含 BOM 的正常 scl_code 不变"""
        normal_scl = "FUNCTION_BLOCK Normal ..."
        assert self._capture_temp_scl(server, normal_scl) == normal_scl.encode("utf-8")

    def test_write_encoding_is_utf8(self, server):
        """写入时使用 utf-8 编码（无 BOM）"""
        source = "FUNCTION_BLOCK 中文编码 ..."
        assert self._capture_temp_scl(server, source) == source.encode("utf-8")
