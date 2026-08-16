"""PLC Gateway 审计链（preview_apply.AuditLog）安全行为回归测试。

覆盖：
- record 互斥（进程内并发写链不分叉）与磁盘锚续链
- TOKEN_CONSUMED / APPLY_* 条目携带脱敏后的 normalized_params 操作载荷
- verify_chain 对损坏行返回报告而非上抛 JSONDecodeError
- clear 同步清磁盘（避免空锚续写断链）
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path

_PROJ = Path(__file__).parent.parent
for p in (str(_PROJ), str(_PROJ / "mcp-servers")):
    if p not in sys.path:
        sys.path.insert(0, p)

from plc_gateway.contracts.preview_apply import (  # noqa: E402
    AuditLog,
    PreviewManager,
    PreviewToken,
)


def _make_manager(log_dir) -> PreviewManager:
    mgr = PreviewManager(ttl=60, secret_key="test-key")
    mgr._audit = AuditLog(log_dir=log_dir, hmac_key="test-key")
    return mgr


def test_record_includes_redacted_params_payload():
    """TOKEN_CONSUMED / APPLY_* 审计条目必须含实际写入的规范化参数，
    凭据类字段脱敏为 [REDACTED]。"""
    with tempfile.TemporaryDirectory() as d:
        mgr = _make_manager(d)
        token = mgr.create_token(
            "tia.block.apply_patch",
            {"block": "FB1", "password": "secret-value", "api_key": "k",
             "operations": [{"operation": "update_network_title"}]},
            "/p", "V21", target_block="FB1",
        )
        consumed = mgr.consume_token(token.token_id, "/p")
        assert consumed is not None
        mgr.apply_started(consumed)
        mgr.apply_succeeded(consumed, "ok")

        for entry in mgr.audit.get_entries():
            params = entry.get("params")
            assert isinstance(params, dict), f"{entry['event']} 缺少 params 载荷"
            assert params["block"] == "FB1"
            assert params["password"] == "[REDACTED]"
            assert params["api_key"] == "[REDACTED]"
            assert params["operations"][0]["operation"] == "update_network_title"

        # 载荷参与 chain_hash：磁盘原始条目与内存条目一致可验链
        assert mgr.audit.verify_chain() == []


def test_concurrent_record_does_not_fork_chain():
    """多线程并发 record：磁盘条目全量落盘且链不分叉。"""
    with tempfile.TemporaryDirectory() as d:
        mgr = _make_manager(d)
        errors: list[Exception] = []

        def worker(n: int) -> None:
            try:
                for i in range(20):
                    token = mgr.create_token("tool", {"w": n, "i": i}, "/p", "V21")
                    mgr.apply_started(token)
            except Exception as exc:  # pragma: no cover - 仅收集失败
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

        log_file = Path(d) / "audit.jsonl"
        lines = [l for l in log_file.read_text(encoding="utf-8").splitlines() if l]
        assert len(lines) == 4 * 20 * 2  # create_token + apply_started
        assert mgr.audit.verify_chain() == []


def test_record_continues_chain_from_disk_across_instances():
    """新 AuditLog 实例（模拟另一进程）接续磁盘链尾，跨实例链可验证。"""
    with tempfile.TemporaryDirectory() as d:
        m1 = _make_manager(d)
        t1 = m1.create_token("tool", {"a": 1}, "/p", "V21")
        m1.apply_started(t1)

        m2 = _make_manager(d)
        t2 = m2.create_token("tool", {"a": 2}, "/p", "V21")
        m2.apply_started(t2)

        assert m2.audit.verify_chain() == []
        assert len(m2.audit.get_entries()) >= 2


def test_verify_chain_reports_corrupt_line_instead_of_raising():
    """磁盘损坏行返回损坏报告（含行号），不再上抛 JSONDecodeError。"""
    with tempfile.TemporaryDirectory() as d:
        mgr = _make_manager(d)
        token = mgr.create_token("tool", {"a": 1}, "/p", "V21")
        mgr.apply_started(token)

        log_file = Path(d) / "audit.jsonl"
        lines = log_file.read_text(encoding="utf-8").splitlines()
        lines.insert(1, "{CORRUPTED")
        log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        broken = mgr.audit.verify_chain()
        assert isinstance(broken, list)
        assert any("error" in b and b["entry"] is None for b in broken)


def test_clear_resets_disk_file():
    """clear 同步删除磁盘文件：清后再追加以空锚续链，链可验证。"""
    with tempfile.TemporaryDirectory() as d:
        mgr = _make_manager(d)
        token = mgr.create_token("tool", {"a": 1}, "/p", "V21")
        mgr.apply_started(token)
        assert (Path(d) / "audit.jsonl").exists()

        mgr.audit.clear()
        assert not (Path(d) / "audit.jsonl").exists()

        token2 = mgr.create_token("tool", {"a": 2}, "/p", "V21")
        mgr.apply_started(token2)
        assert mgr.audit.verify_chain() == []
        # 新实例从磁盘加载的是 clear 后的新链
        fresh = _make_manager(d)
        assert len(fresh.audit.get_entries()) == 2


def test_record_persist_failure_keeps_memory_consistent(tmp_path, monkeypatch):
    """_persist 失败（fail-closed 抛出）时不更新内存锚与条目窗口。"""
    mgr = _make_manager(tmp_path)
    token = mgr.create_token("tool", {"a": 1}, "/p", "V21")
    before_entries = len(mgr.audit.get_entries())
    before_hash = mgr.audit._last_hash

    def _fail(entry):
        raise RuntimeError("审计日志写入失败")

    monkeypatch.setattr(mgr.audit, "_persist", _fail)
    try:
        mgr.apply_started(token)
    except RuntimeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("写入失败必须上抛")

    assert len(mgr.audit.get_entries()) == before_entries
    assert mgr.audit._last_hash == before_hash


def test_record_fail_closed_on_corrupted_tail(tmp_path):
    """磁盘链尾损坏时 record 拒绝静默重锚（fail-closed 抛出）。"""
    mgr = _make_manager(tmp_path)
    token = mgr.create_token("tool", {"a": 1}, "/p", "V21")

    log_file = tmp_path / "audit.jsonl"
    # 用不可解析且无法从尾部恢复的内容覆盖
    log_file.write_text("not-json-at-all\n", encoding="utf-8")

    try:
        mgr.apply_started(token)
    except RuntimeError as exc:
        assert "拒绝静默重锚" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("链尾损坏必须 fail-closed 拒绝写入")
