"""确认请求存储（ConfirmationRequestStore）的持久化健壮性测试。"""

import json
import os
from pathlib import Path

import pytest

from safety.confirmation_requests import ConfirmationRequestStore


class _StubService:
    """只提供 issue() 的最小 stub，隔离真实 ConfirmationService。"""

    def __init__(self):
        self.issued = []

    def issue(self, **kwargs):
        self.issued.append(kwargs)
        return "stub-token"


def _make_store(tmp_path: Path, content: str | None = None) -> ConfirmationRequestStore:
    path = tmp_path / "requests.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    return ConfirmationRequestStore(path, service=_StubService())


class TestCorruptFileRecovery:
    """损坏文件必须改名留痕后从空队列恢复，不得静默清空。"""

    def test_invalid_json_renamed_and_recovered(self, tmp_path):
        path = tmp_path / "requests.json"
        path.write_text("{ not valid json", encoding="utf-8")

        store = ConfirmationRequestStore(path, service=_StubService())

        assert store.list() == []
        assert not path.exists()  # 原文件已改名移走
        leftovers = list(tmp_path.glob("requests.json.corrupt-*"))
        assert len(leftovers) == 1
        assert leftovers[0].read_text(encoding="utf-8") == "{ not valid json"

    def test_non_dict_json_renamed_and_recovered(self, tmp_path):
        path = tmp_path / "requests.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")

        store = ConfirmationRequestStore(path, service=_StubService())

        assert store.list() == []
        assert len(list(tmp_path.glob("requests.json.corrupt-*"))) == 1

    def test_recovery_then_persist_new_request(self, tmp_path):
        path = tmp_path / "requests.json"
        path.write_text("broken", encoding="utf-8")

        store = ConfirmationRequestStore(path, service=_StubService())
        record = store.create("demo_workflow", "desc")

        # 恢复后新请求正常落盘，且损坏现场仍保留
        data = json.loads(path.read_text(encoding="utf-8"))
        assert record["request_id"] in data
        assert len(list(tmp_path.glob("requests.json.corrupt-*"))) == 1


class TestAtomicSave:
    """_save 必须临时文件 + 原子替换，且失败时上抛。"""

    def test_save_leaves_no_tmp_residue(self, tmp_path):
        store = _make_store(tmp_path)
        store.create("demo_workflow")

        assert len(list(tmp_path.glob("*.tmp-*"))) == 0
        data = json.loads((tmp_path / "requests.json").read_text(encoding="utf-8"))
        assert len(data) == 1

    def test_save_failure_raises(self, tmp_path, monkeypatch):
        store = _make_store(tmp_path)

        def broken_replace(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", broken_replace)
        with pytest.raises(OSError, match="disk full"):
            store.create("demo_workflow")

    def test_failed_save_cleans_tmp_file(self, tmp_path, monkeypatch):
        store = _make_store(tmp_path)

        def broken_replace(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", broken_replace)
        with pytest.raises(OSError):
            store.create("demo_workflow")
        assert len(list(tmp_path.glob("*.tmp-*"))) == 0


class TestWorkflowRegression:
    """create/approve/deny/take_token 常规流程回归。"""

    def test_create_approve_take_token_flow(self, tmp_path):
        store = _make_store(tmp_path)

        record = store.create("nl_to_plcsim_pipeline", "demo")
        assert record["status"] == "pending"

        approved = store.approve(record["request_id"], "human-1")
        assert approved["confirmation_token"] == "stub-token"

        token = store.take_token(record["request_id"])
        assert token == "stub-token"
        # 一次性领取：再次领取返回 None
        assert store.take_token(record["request_id"]) is None

    def test_deny_flow(self, tmp_path):
        store = _make_store(tmp_path)
        record = store.create("wf")

        result = store.deny(record["request_id"], "human-1")
        assert result["status"] == "denied"
        with pytest.raises(ValueError):
            store.approve(record["request_id"], "human-1")

    def test_state_survives_reload(self, tmp_path):
        path = tmp_path / "requests.json"
        service = _StubService()
        store = ConfirmationRequestStore(path, service=service)
        record = store.create("wf")

        reloaded = ConfirmationRequestStore(path, service=_StubService())
        assert reloaded.get(record["request_id"])["status"] == "pending"
