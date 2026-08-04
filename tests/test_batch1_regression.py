"""
Batch 1 回归测试 — 路径校验、统一返回格式

覆盖：
  - B1.1: _resolve_path 拒绝非配置项目路径
  - B1.3: _make_result 统一返回格式
  - B1.1: create_ladder_block 内部调用 _resolve_path 后才导入

注意：本文件与现有 test_server_tools.py 共存，使用 importlib.reload 确保
模块隔离，避免与其他测试的 sys.modules 管理冲突。
"""
import json
import importlib
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

_PROJECT = Path(__file__).parent.parent
_TIA_MCP = _PROJECT / "mcp-servers" / "tia-mcp"
sys.path.insert(0, str(_TIA_MCP))
sys.path.insert(0, str(_PROJECT))

# 确保测试环境变量
os.environ.setdefault("MCP_AUTH_TOKEN", "pytest-mcp-auth-token")
os.environ.setdefault("AI_PLC_OFFLINE_TESTING", "1")


# ── 直接测试 _make_result 逻辑（纯函数，不依赖模块导入） ──

def _make_result(
    ok: bool = True,
    *,
    operation: str = "",
    result=None,
    warnings=None,
    error: str | None = None,
    reconcile_required: bool = False,
    operation_id: str = "",
    extra: dict | None = None,
) -> dict:
    """内联复现 server.py 的 _make_result 逻辑"""
    import uuid
    if not operation_id:
        operation_id = uuid.uuid4().hex
    ret = {
        "ok": ok,
        "status": "success" if ok else "error",
        "operation": operation,
        "operation_id": operation_id,
        "result": result if result is not None else {},
        "warnings": warnings or [],
        "error": error if not ok else None,
        "reconcile_required": reconcile_required,
    }
    if extra:
        ret.update(extra)
    return ret


class TestMakeResult:
    """测试统一返回格式（验证 server.py 中 _make_result 的行为契约）"""

    def test_success_default(self):
        r = _make_result(ok=True, operation="test.op")
        assert r["ok"] is True
        assert r["status"] == "success"
        assert r["operation"] == "test.op"
        assert "operation_id" in r
        assert r["result"] == {}
        assert r["warnings"] == []
        assert r["error"] is None
        assert r["reconcile_required"] is False

    def test_error(self):
        r = _make_result(ok=False, operation="test.op", error="something went wrong")
        assert r["ok"] is False
        assert r["status"] == "error"
        assert r["error"] == "something went wrong"
        assert r["reconcile_required"] is False

    def test_with_result_data(self):
        r = _make_result(ok=True, operation="test.op", result={"key": "value"})
        assert r["result"]["key"] == "value"

    def test_with_warnings(self):
        r = _make_result(ok=True, operation="test.op", warnings=["warn1"])
        assert r["warnings"] == ["warn1"]

    def test_reconcile_required(self):
        r = _make_result(ok=False, operation="test.op", error="timeout", reconcile_required=True)
        assert r["reconcile_required"] is True
        assert r["ok"] is False

    def test_extra_fields(self):
        r = _make_result(ok=True, operation="test.op", extra={"extra_field": "extra"})
        assert r["extra_field"] == "extra"

    def test_operation_id_unique(self):
        r1 = _make_result(ok=True, operation="test.op")
        r2 = _make_result(ok=True, operation="test.op")
        assert r1["operation_id"] != r2["operation_id"]

    def test_operation_id_custom(self):
        r = _make_result(ok=True, operation="test.op", operation_id="custom-id")
        assert r["operation_id"] == "custom-id"


# ── 模块级测试：server.py 的 _resolve_path 和 _make_result ──


@pytest.fixture(scope="module")
def _server_module():
    """单次导入 server 模块（模块级），供所有测试共享"""
    # Mock Windows 特有模块
    _mock_modules = {
        "clr": MagicMock(),
        "Siemens": MagicMock(),
        "Siemens.Engineering": MagicMock(),
        "System": MagicMock(),
        "System.IO": MagicMock(),
        "safety": MagicMock(),
        "safety.validator": MagicMock(),
        "audit": MagicMock(),
        "ladder_renderer": MagicMock(),
        "config_loader": MagicMock(),
    }
    _mock_validator = MagicMock()
    _mock_validator.validate.return_value = MagicMock(allowed=True, reason="")
    _mock_modules["safety.validator"].validator = _mock_validator
    _mock_modules["safety.validator"].validate.return_value = MagicMock(allowed=True, reason="")

    # Mock config_loader
    _mock_config = MagicMock()
    _mock_target = MagicMock()
    _mock_target.profile = "isolated_plcsim_v21"
    _mock_target.tia_version = "V21"
    _mock_target.project_path = "D:/test/TEST_PROJECT.ap21"
    _mock_target.plcsim_instance = "Siemens PLCSIM Virtual Ethernet Adapter"
    _mock_target.plc_ip = "192.168.0.1"
    _mock_config.target = _mock_target
    _mock_config.tia.project_path = "D:/test/TEST_PROJECT.ap21"
    _mock_config.tia.install_dir = "C:/Program Files/Siemens/Automation"
    _mock_config.tia.version = "V21"
    _mock_modules["config_loader"].cfg = _mock_config
    _mock_modules["config_loader"].validate_control_target.return_value = _mock_target
    _mock_modules["config_loader"].TargetConfigurationError = type("TargetConfigurationError", (Exception,), {})

    _missing = object()
    _shadowed_names = (*_mock_modules, "server")
    _original_modules = {
        key: sys.modules.get(key, _missing)
        for key in _shadowed_names
    }
    try:
        sys.modules.pop("server", None)
        for key, mock in _mock_modules.items():
            sys.modules[key] = mock

        import server as sv
        importlib.reload(sv)
        yield sv
    finally:
        for key, original in _original_modules.items():
            if original is _missing:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


@pytest.fixture
def sv(_server_module):
    """返回已导入的 server 模块"""
    return _server_module


# ── B1.3: 验证 server.py 中存在 _make_result ──


class TestServerMakeResult:
    """验证 server.py 模块包含 _make_result 函数"""

    def test_module_has_make_result(self, sv):
        assert hasattr(sv, "_make_result"), "server.py 缺少 _make_result 函数"

    def test_module_has_make_result_returns_dict(self, sv):
        r = sv._make_result(ok=True, operation="test.op")
        assert r["ok"] is True
        assert r["status"] == "success"

    def test_module_has_make_result_error(self, sv):
        r = sv._make_result(ok=False, operation="test.op", error="fail")
        assert r["ok"] is False
        assert r["error"] == "fail"


# ── B1.1: 路径校验 ──


class TestResolvePath:
    """测试 _resolve_path 拒绝非配置项目路径"""

    def test_accepts_empty_path(self, sv):
        # 空路径表示使用唯一配置路径（默认项目路径）
        path = sv._resolve_path("")
        assert path == "D:/test/TEST_PROJECT.ap21"

    def test_rejects_non_configured_path(self, sv):
        with pytest.raises(ValueError, match="拒绝非唯一配置中的 TIA 项目路径"):
            sv._resolve_path("D:/some/other/project.ap21")

    def test_accepts_configured_path(self, sv):
        # 显式传入配置中的项目路径也必须被接受（与空路径测试区分）
        path = sv._resolve_path("D:/test/TEST_PROJECT.ap21")
        assert path == "D:/test/TEST_PROJECT.ap21"


# ── B1.1: create_ladder_block 路径绕过修复 ──


class TestCreateLadderBlockPathGuard:
    """测试 create_ladder_block 的路径校验与梯形图语义安全链"""

    @patch("server._import_xml_into_tia")
    @patch("server._run_cartgen")
    @patch("server._gen_lad_spec")
    def test_non_configured_path_rejected(
        self, mock_gen, mock_cartgen, mock_import, sv
    ):
        mock_gen.return_value = {"blockName": "TestBlock", "networks": []}
        mock_cartgen.return_value = "/tmp/test.xml"

        # 调用 create_ladder_block 时传入非配置路径
        # （不 patch _require_ladder_semantic_safety：路径校验先于语义安全链，
        #   非配置路径必须在 _gen_lad_spec 之前被拒绝）
        result = sv.create_ladder_block(
            description="test block",
            block_name="TestBlock",
            project_path="D:/some/evil/project.ap21",
            auth_token="pytest-mcp-auth-token",
        )

        # 验证：路径被拒绝，且拒绝必须来自路径校验本身（严格断言具体错误，
        #   避免把认证失败/语义安全链拒绝等无关环节误判为路径校验生效）
        assert result.get("ok") is False
        assert "拒绝非唯一配置中的 TIA 项目路径" in result.get("error", "")
        # 路径校验必须先于 LAD 生成/语义安全链/工程态写入拦截（fail-closed）
        mock_gen.assert_not_called()
        mock_cartgen.assert_not_called()
        mock_import.assert_not_called()

    @patch("server._import_xml_into_tia")
    @patch("server._run_cartgen")
    @patch("server._gen_lad_spec")
    def test_semantic_safety_failure_blocks_import(
        self, mock_gen, mock_cartgen, mock_import, sv
    ):
        """LadderSpec 语义安全校验失败必须在 CartGen/TIA 导入前阻断（fail-closed）"""
        mock_gen.return_value = {"blockName": "UnsafeMotor", "networks": []}
        mock_cartgen.return_value = "/tmp/test.xml"

        # 语义安全链返回不安全 → _require_ladder_semantic_safety 必须抛错阻断
        with patch.object(sv, "safety_validate_ladder", return_value={
            "safe": False,
            "warnings": ["电机类输出块缺少急停互锁引用（变量名须含 stop/emergency）"],
        }):
            result = sv.create_ladder_block(
                description="电机正反转，带急停和过载",
                block_name="UnsafeMotor",
                project_path="",  # 空路径 → 唯一配置路径，路径校验通过
                auth_token="pytest-mcp-auth-token",
            )

        # 验证：语义安全校验失败 → 阻断，CartGen 与 TIA 导入均未被调用
        assert result.get("ok") is False
        assert "语义安全校验失败" in result.get("error", "")
        mock_cartgen.assert_not_called()
        mock_import.assert_not_called()

    @patch("server._import_xml_into_tia")
    @patch("server._run_cartgen")
    @patch("server._gen_lad_spec")
    def test_safety_gate_fail_closed_when_validator_denies(
        self, mock_gen, mock_cartgen, mock_import, sv
    ):
        """validator 拒绝时必须 fail-closed 阻断，不允许进入工程态操作"""
        mock_gen.return_value = {"blockName": "TestBlock", "networks": []}
        mock_cartgen.return_value = "/tmp/test.xml"

        # validator 熔断 → _safety_gate 必须返回阻断结果
        with patch.object(
            sv.safety_validator, "validate",
            return_value=MagicMock(allowed=False, reason="断路器已熔断"),
        ):
            result = sv.create_ladder_block(
                description="test block",
                block_name="TestBlock",
                project_path="D:/test/TEST_PROJECT.ap21",
                auth_token="pytest-mcp-auth-token",
            )

        assert result.get("ok") is False
        assert "安全链拒绝" in result.get("error", "")
        mock_import.assert_not_called()
