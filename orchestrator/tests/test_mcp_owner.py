import json

import pytest

from orchestrator.mcp_owner import McpOwnerBusyError, McpOwnerLock


def test_mcp_owner_lock_excludes_a_second_owner_and_releases_cleanly(tmp_path):
    lock_path = tmp_path / "mcp-owner.lock"
    first = McpOwnerLock("backend", lock_path=lock_path)
    second = McpOwnerLock("standalone-orchestrator", lock_path=lock_path)

    first.acquire()
    metadata = json.loads(lock_path.read_text(encoding="utf-8"))
    with pytest.raises(McpOwnerBusyError):
        second.acquire()
    first.release()

    assert metadata["owner"] == "backend"
    assert not lock_path.exists()


def test_mcp_owner_lock_release_is_idempotent(tmp_path):
    lock_path = tmp_path / "mcp-owner.lock"
    owner = McpOwnerLock("backend", lock_path=lock_path)
    owner.acquire()
    owner.release()
    owner.release()

    assert not lock_path.exists()
