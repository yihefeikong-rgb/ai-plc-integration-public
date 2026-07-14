"""控制类 TiaWorker 操作的幂等性与下载成功条件。"""

import json
import subprocess
from pathlib import Path

from mcp_common.tiaworker_client import TiaWorkerClient


def test_mutating_timeout_is_not_retried_and_requires_reconciliation(tmp_path, monkeypatch):
    """下载可能已落到设备；超时后绝不能盲目再次执行。"""
    worker = tmp_path / "TiaWorker.exe"
    worker.touch()
    calls = []

    def timeout(*args, **kwargs):
        calls.append(args[0])
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr("mcp_common.tiaworker_client.subprocess.run", timeout)
    result = TiaWorkerClient(worker).run("download", {"ProjectPath": "demo.ap21"}, max_retries=3)

    assert len(calls) == 1
    assert result["success"] is False
    assert result["error_code"] == "OUTCOME_UNKNOWN"
    assert result["reconcile_required"] is True
    assert result["operation_id"]


def test_readonly_timeout_keeps_bounded_retry(tmp_path, monkeypatch):
    """只读查询仍可使用有限重试。"""
    worker = tmp_path / "TiaWorker.exe"
    worker.touch()
    calls = []

    def timeout(*args, **kwargs):
        calls.append(args[0])
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr("mcp_common.tiaworker_client.subprocess.run", timeout)
    result = TiaWorkerClient(worker).run("list-blocks", {"ProjectPath": "demo.ap21"}, max_retries=1)

    assert len(calls) == 2
    assert result["error_code"] == "TIMEOUT"
    assert "reconcile_required" not in result


def test_mutating_operation_id_is_forwarded_to_worker_and_returned(tmp_path, monkeypatch):
    """变更请求携带稳定操作 ID，供后续只读对账使用。"""
    worker = tmp_path / "TiaWorker.exe"
    worker.touch()
    received = {}

    class Completed:
        stdout = json.dumps({"ok": True, "result": {"saved": "demo"}})
        returncode = 0

    def complete(cmd, **kwargs):
        with open(cmd[-1], encoding="utf-8") as handle:
            received.update(json.load(handle))
        return Completed()

    monkeypatch.setattr("mcp_common.tiaworker_client.subprocess.run", complete)
    result = TiaWorkerClient(worker).run(
        "import-block",
        {"ProjectPath": "demo.ap21"},
        operation_id="op-123",
    )

    assert received["OperationId"] == "op-123"
    assert result["operation_id"] == "op-123"


def test_mutating_unparseable_result_is_treated_as_outcome_unknown(tmp_path, monkeypatch):
    """进程返回不可解析文本时，也不能假定下载没有发生。"""
    worker = tmp_path / "TiaWorker.exe"
    worker.touch()

    class Completed:
        stdout = "not-json"
        returncode = 0

    monkeypatch.setattr(
        "mcp_common.tiaworker_client.subprocess.run",
        lambda *args, **kwargs: Completed(),
    )
    result = TiaWorkerClient(worker).run("download", {"ProjectPath": "demo.ap21"})

    assert result["error_code"] == "OUTCOME_UNKNOWN"
    assert result["reconcile_required"] is True


def test_worker_download_requires_explicit_device_level_success():
    """缺少设备级回执时，下载结果必须视为未知而不是成功。"""
    from download_to_plcsim import is_confirmed_device_download

    assert is_confirmed_device_download({
        "ok": True,
        "result": {
            "success": True,
            "deviceState": "downloaded",
            "operationId": "op-123",
        },
    }) is True
    assert is_confirmed_device_download({"ok": True, "result": {"success": True}}) is False
    assert is_confirmed_device_download({"status": "ok", "data": {"success": True}}) is False
