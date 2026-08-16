"""PLC Gateway 受控 Apply（guarded_apply）确认令牌模型回归测试。

锁定：布尔 confirmed 不再放行；必须消费 PreviewManager 签发的一次性
确认令牌；令牌消费发生在全部只读检查（TOCTOU 等）通过之后。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PROJ = Path(__file__).parent.parent
for p in (str(_PROJ), str(_PROJ / "mcp-servers")):
    if p not in sys.path:
        sys.path.insert(0, p)

from plc_gateway.contracts.preview_apply import (  # noqa: E402
    AuditLog,
    PreviewManager,
)
from plc_gateway.providers.base import ProviderResult  # noqa: E402
from plc_gateway.workflows.guarded_apply import (  # noqa: E402
    BlockSnapshot,
    NetworkSnapshot,
    _extract_networks,
    _hash_content,
    guarded_apply_execute,
)

_NS = "http://www.siemens.com/automation/Openness/SW/Motion/Networks/v1"


def _xml(title: str) -> str:
    return (
        f'<Document xmlns:n="{_NS}">'
        f'<n:Network><n:NetworkTitle><n:Title>{title}</n:Title></n:NetworkTitle>'
        f'<n:Comment><n:Title>c</n:Title></n:Comment></n:Network>'
        f"</Document>"
    )


def _make_snapshot(block: str, xml: str) -> BlockSnapshot:
    networks = [
        NetworkSnapshot(index=n["index"], title=n["title"],
                        comment=n["comment"], content_hash=n["hash"])
        for n in _extract_networks(xml)
    ]
    return BlockSnapshot(block_name=block, original_xml=xml,
                         block_hash=_hash_content(xml), networks=networks)


@pytest.fixture
def manager(tmp_path, monkeypatch):
    """隔离的 PreviewManager（临时审计目录），注入 guarded_apply 模块。"""
    mgr = PreviewManager(ttl=60, secret_key="test-key")
    mgr._audit = AuditLog(log_dir=tmp_path, hmac_key="test-key")
    import plc_gateway.workflows.guarded_apply as ga
    monkeypatch.setattr(ga, "get_preview_manager", lambda: mgr)
    return mgr


@pytest.fixture
def provider():
    p = MagicMock()
    p.name = "tiacommander"
    return p


_PATCH = {"block": "FB10", "operations": [
    {"operation": "update_network_title", "network_index": 0}]}


async def _execute(provider, manager, *, snapshot, patch=_PATCH,
                   confirmation_token="", compile_after=False,
                   project_path="/proj/demo.ap21"):
    return await guarded_apply_execute(
        provider, patch["block"], patch,
        confirmation_token=confirmation_token,
        compile_after=compile_after,
        snapshot=snapshot,
        project_path=project_path,
    )


class TestConfirmationTokenRequired:
    @pytest.mark.asyncio
    async def test_missing_token_rejected(self, provider, manager):
        """缺令牌直接拒绝（布尔放行已移除）。"""
        result = await _execute(provider, manager,
                                snapshot=_make_snapshot("FB10", _xml("old")))
        assert result["ok"] is False
        assert "缺少确认令牌" in result["errors"][0]
        provider.apply_patch.assert_not_called()

    @pytest.mark.asyncio
    async def test_boolean_style_confirmation_not_accepted(self, provider, manager):
        """调用方传 confirmed=True 风格的关键字不再存在放行语义。"""
        import inspect
        from plc_gateway.workflows.guarded_apply import guarded_apply_execute as fn
        assert "confirmed" not in inspect.signature(fn).parameters


class TestTokenConsumedAfterReadOnlyChecks:
    @pytest.mark.asyncio
    async def test_block_drift_does_not_burn_token(self, provider, manager):
        """TOCTOU 漂移在消费令牌之前拒绝：令牌保持可复用。"""
        pre = _xml("old")
        snapshot = _make_snapshot("FB10", pre)
        token = manager.create_token("guarded_apply.execute", _PATCH,
                                     "/proj/demo.ap21", "V21")
        # 当前块 XML 与快照不一致 → 漂移
        provider.get_block_xml.return_value = ProviderResult(
            ok=True, result={"xml": _xml("drifted")})
        result = await _execute(provider, manager, snapshot=snapshot,
                                confirmation_token=token.token_id)
        assert result["ok"] is False
        assert not token.used
        provider.apply_patch.assert_not_called()

    @pytest.mark.asyncio
    async def test_happy_path_consumes_token_once(self, provider, manager):
        """全部通过：令牌恰好消费一次，重放被拒。"""
        pre, post = _xml("old"), _xml("new")
        snapshot = _make_snapshot("FB10", pre)
        token = manager.create_token("guarded_apply.execute", _PATCH,
                                     "/proj/demo.ap21", "V21")
        provider.get_block_xml.side_effect = [
            ProviderResult(ok=True, result={"xml": pre}),
            ProviderResult(ok=True, result={"xml": post}),
        ]
        provider.apply_patch.return_value = ProviderResult(
            ok=True, operation="guarded_apply.execute")

        result = await _execute(provider, manager, snapshot=snapshot,
                                confirmation_token=token.token_id)
        assert result["ok"] is True
        assert result["network_matches"][0]["modified"] is True
        assert token.used

        # 重放同一令牌：已消费，拒绝
        provider.get_block_xml.side_effect = [
            ProviderResult(ok=True, result={"xml": pre}),
            ProviderResult(ok=True, result={"xml": post}),
        ]
        replay = await _execute(provider, manager, snapshot=snapshot,
                                confirmation_token=token.token_id)
        assert replay["ok"] is False

    @pytest.mark.asyncio
    async def test_unsigned_token_rejected(self, provider, manager, monkeypatch):
        """未签名令牌（无 HMAC 密钥签发）拒绝执行。"""
        pre = _xml("old")
        snapshot = _make_snapshot("FB10", pre)
        # 用空 secret 的 manager 签发 → token.signature 为空
        unsigned_mgr = PreviewManager(ttl=60, secret_key="")
        unsigned_mgr._audit = manager._audit
        import plc_gateway.workflows.guarded_apply as ga
        monkeypatch.setattr(ga, "get_preview_manager", lambda: unsigned_mgr)
        token = unsigned_mgr.create_token("guarded_apply.execute", _PATCH,
                                          "/proj/demo.ap21", "V21")
        assert token.signature == ""

        provider.get_block_xml.return_value = ProviderResult(
            ok=True, result={"xml": pre})
        result = await _execute(provider, manager, snapshot=snapshot,
                                confirmation_token=token.token_id)
        assert result["ok"] is False
        assert "未签名" in result["errors"][0]
        provider.apply_patch.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_failure_audited(self, provider, manager):
        """apply_patch 失败写入审计链（APPLY_FAILED）。"""
        pre = _xml("old")
        snapshot = _make_snapshot("FB10", pre)
        token = manager.create_token("guarded_apply.execute", _PATCH,
                                     "/proj/demo.ap21", "V21")
        provider.get_block_xml.return_value = ProviderResult(
            ok=True, result={"xml": pre})
        provider.apply_patch.return_value = ProviderResult(
            ok=False, error="TiaCommander 应用失败")

        result = await _execute(provider, manager, snapshot=snapshot,
                                confirmation_token=token.token_id)
        assert result["ok"] is False
        events = [e["event"] for e in manager.audit.get_entries()]
        assert "token_consumed" in events
        assert "apply_started" in events
        assert "apply_failed" in events
