"""PLC Gateway 安全链（safety_chain / preview_apply 令牌绑定）回归测试。

覆盖：
- check_all 只读检查失败时不消费一次性确认令牌（先检查后消费）
- "token 有绑定就必须验证"：令牌记录了非空绑定而调用方未提供当前值
  时 fail-closed 拒绝，不再静默跳过
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_PROJ = Path(__file__).parent.parent
for p in (str(_PROJ), str(_PROJ / "mcp-servers")):
    if p not in sys.path:
        sys.path.insert(0, p)

from plc_gateway.contracts.preview_apply import (  # noqa: E402
    AuditLog,
    PreviewManager,
)
from plc_gateway.contracts.safety_chain import SafetyChain  # noqa: E402
from plc_gateway.policy.risk_levels import RiskLevel  # noqa: E402


def _make_chain(log_dir, secret: str = "test-key") -> SafetyChain:
    mgr = PreviewManager(ttl=60, secret_key=secret)
    mgr._audit = AuditLog(log_dir=log_dir, hmac_key=secret)
    chain = SafetyChain({"secret_key": secret})
    chain.set_preview_manager(mgr)
    return chain


def _issue_confirmation(chain: SafetyChain, **kwargs):
    return chain.preview_manager.create_token(
        "tia.block.apply_patch", {"block": "FB1"}, "/proj/demo.ap21", "V21",
        operator="op", confirmer="human", **kwargs)


class TestCheckAllConsumesTokenLast:
    def test_target_mismatch_does_not_burn_confirmation(self):
        """目标检查失败时确认令牌不得被消费（仍可复用）。"""
        with tempfile.TemporaryDirectory() as d:
            chain = _make_chain(d)
            preview = _issue_confirmation(chain)
            token = _issue_confirmation(chain)

            # 项目路径与配置不一致 → check_target 失败
            result = chain.check_all(
                "/other/project.ap21", "/proj/demo.ap21",
                RiskLevel.L2_TIA_EDIT,
                preview_token=preview.token_id,
                confirmation_token=token.token_id,
            )
            assert not result.allowed

            # 令牌未被烧毁：修正目标后可用同一令牌通过
            result2 = chain.check_all(
                "/proj/demo.ap21", "/proj/demo.ap21",
                RiskLevel.L2_TIA_EDIT,
                preview_token=preview.token_id,
                confirmation_token=token.token_id,
            )
            assert result2.allowed

    def test_risk_disabled_does_not_burn_confirmation(self):
        """L4 默认禁用的拒绝同样不得消费确认令牌。"""
        with tempfile.TemporaryDirectory() as d:
            chain = _make_chain(d)
            token = _issue_confirmation(chain)

            result = chain.check_all(
                "/proj/demo.ap21", "/proj/demo.ap21",
                RiskLevel.L4_REAL_DEVICE,
                confirmation_token=token.token_id,
            )
            assert not result.allowed
            assert not token.used

    def test_invalid_preview_token_does_not_burn_confirmation(self):
        """L2 需要预览：预览令牌无效时确认令牌不被消费。"""
        with tempfile.TemporaryDirectory() as d:
            chain = _make_chain(d)
            confirmation = _issue_confirmation(chain)
            # 预览令牌不存在
            result = chain.check_all(
                "/proj/demo.ap21", "/proj/demo.ap21",
                RiskLevel.L2_TIA_EDIT,
                preview_token="nonexistent",
                confirmation_token=confirmation.token_id,
            )
            assert not result.allowed
            assert not confirmation.used

    def test_confirmation_token_same_as_preview_rejected_before_consume(self):
        """确认令牌与预览令牌相同的检查在消费之前执行。"""
        with tempfile.TemporaryDirectory() as d:
            chain = _make_chain(d)
            token = _issue_confirmation(chain, target_hash="h" * 64)
            result = chain.check_all(
                "/proj/demo.ap21", "/proj/demo.ap21",
                RiskLevel.L2_TIA_EDIT,
                preview_token=token.token_id,
                confirmation_token=token.token_id,
            )
            assert not result.allowed
            assert not token.used

    def test_happy_path_consumes_once(self):
        """全部通过时确认令牌恰好消费一次，重放被拒。"""
        with tempfile.TemporaryDirectory() as d:
            chain = _make_chain(d)
            preview = _issue_confirmation(chain)
            confirmation = _issue_confirmation(chain)
            args = dict(
                project_path="/proj/demo.ap21",
                configured_project="/proj/demo.ap21",
                risk_level=RiskLevel.L2_TIA_EDIT,
                preview_token=preview.token_id,
            )
            assert chain.check_all(
                confirmation_token=confirmation.token_id, **args).allowed
            # 重放：令牌已消费必须被拒
            assert not chain.check_all(
                confirmation_token=confirmation.token_id, **args).allowed


class TestTokenBindingEnforcement:
    def test_bound_project_path_requires_current_value(self):
        """令牌绑定 project_path 而调用方未提供当前值 → 拒绝。"""
        with tempfile.TemporaryDirectory() as d:
            chain = _make_chain(d)
            token = _issue_confirmation(chain)  # project_path="/proj/demo.ap21"
            mgr = chain.preview_manager
            assert mgr.validate_token(token.token_id) is None
            assert mgr.validate_token(token.token_id, "/proj/demo.ap21") is not None

    def test_bound_target_hash_requires_current_value(self):
        """令牌绑定 target_hash 而调用方未提供当前 hash → 拒绝。"""
        with tempfile.TemporaryDirectory() as d:
            chain = _make_chain(d)
            token = _issue_confirmation(chain, target_hash="a" * 64)
            mgr = chain.preview_manager
            # 只提供 project_path，缺少当前 hash：拒绝
            assert mgr.validate_token(token.token_id, "/proj/demo.ap21") is None
            # 提供全部绑定当前值：通过
            assert mgr.validate_token(
                token.token_id, "/proj/demo.ap21", "a" * 64) is not None

    def test_bound_device_id_requires_current_value(self):
        """令牌绑定 device_id 而调用方未提供当前设备 → 拒绝。"""
        with tempfile.TemporaryDirectory() as d:
            chain = _make_chain(d)
            token = _issue_confirmation(chain, device_id="plcsim:factoryio")
            mgr = chain.preview_manager
            assert mgr.validate_token(
                token.token_id, "/proj/demo.ap21") is None
            assert mgr.validate_token(
                token.token_id, "/proj/demo.ap21",
                current_device_id="plcsim:factoryio",
            ) is not None

    def test_mismatched_binding_rejected(self):
        """绑定的当前值与令牌记录不一致 → 拒绝（原有语义保持）。"""
        with tempfile.TemporaryDirectory() as d:
            chain = _make_chain(d)
            token = _issue_confirmation(chain)
            mgr = chain.preview_manager
            assert mgr.validate_token(
                token.token_id, "/other/demo.ap21") is None

    def test_unbound_token_still_validates_without_optional_values(self):
        """未绑定 target_hash/device_id 的令牌不强制提供可选项。"""
        with tempfile.TemporaryDirectory() as d:
            chain = _make_chain(d)
            token = _issue_confirmation(chain)
            mgr = chain.preview_manager
            # 仅提供必绑定的 project_path 即可通过
            assert mgr.validate_token(token.token_id, "/proj/demo.ap21") is not None
