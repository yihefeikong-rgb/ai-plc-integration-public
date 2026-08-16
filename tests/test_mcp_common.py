"""
mcp_common 核心模块测试 — 连接管理 / 审计日志 / TiaWorker 客户端
"""

import os
import sys
import tempfile
import threading
import pytest
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))


class TestConnectionManager:
    """ConnectionManager 双锁测试"""

    def test_get_sync_returns_connection(self):
        from mcp_common.connection import ConnectionManager
        mgr = ConnectionManager(connect_fn=lambda: "hello")
        result = mgr.get_sync()
        assert result == "hello"
        # 二次调用返回缓存
        assert mgr.get_sync() == "hello"

    def test_get_sync_thread_safe(self):
        from mcp_common.connection import ConnectionManager
        counter = [0]

        def make_connection():
            counter[0] += 1
            return f"conn_{counter[0]}"

        mgr = ConnectionManager(connect_fn=make_connection)
        results = []

        def worker():
            results.append(mgr.get_sync())

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有线程应该得到同一个连接
        assert len(set(results)) == 1

    def test_reset_creates_new_connection(self):
        from mcp_common.connection import ConnectionManager
        counter = [0]

        def make_connection():
            counter[0] += 1
            return f"conn_{counter[0]}"

        mgr = ConnectionManager(connect_fn=make_connection)
        assert mgr.get_sync() == "conn_1"
        mgr.reset()
        assert mgr.get_sync() == "conn_2"

    def test_connected_property(self):
        from mcp_common.connection import ConnectionManager
        mgr = ConnectionManager(connect_fn=lambda: "x")
        assert not mgr.connected
        mgr.get_sync()
        assert mgr.connected
        mgr.reset()
        assert not mgr.connected


class TestAuditHMAC:
    """审计日志 HMAC 链式验证测试"""

    def test_audit_chain_integrity(self):
        from mcp_common.audit import AuditLogger
        fd, tmp_path = tempfile.mkstemp(suffix='.jsonl')
        os.close(fd)
        try:
            logger = AuditLogger(log_path=tmp_path)
            r1 = logger.log("write", "tag1", "value1")
            r2 = logger.log("write", "tag2", "value2")
            r3 = logger.log_operation("op", key="val")

            assert len(r1["hash"]) == 64
            assert r2["prev_hash"] == r1["hash"]
            assert r3["prev_hash"] == r2["hash"]

            # 验证链完整
            assert logger.verify()
        finally:
            os.unlink(tmp_path)

    def test_audit_tamper_detection(self):
        from mcp_common.audit import AuditLogger
        fd, tmp_path = tempfile.mkstemp(suffix='.jsonl')
        os.close(fd)
        try:
            logger = AuditLogger(log_path=tmp_path)
            logger.log("write", "tag1", "value1")
            logger.log("write", "tag2", "value2")

            # 篡改日志
            with open(tmp_path, "a", encoding="utf-8") as f:
                f.write('{"forged": true}\n')

            assert not logger.verify()
        finally:
            os.unlink(tmp_path)

    def test_audit_lazy_proxy(self):
        from mcp_common.audit import audit
        # 代理对象支持属性访问
        assert hasattr(audit, "log")
        assert hasattr(audit, "log_operation")
        assert hasattr(audit, "verify")

    def test_read_logs_empty(self):
        from mcp_common.audit import AuditLogger
        fd, tmp_path = tempfile.mkstemp(suffix='.jsonl')
        os.close(fd)
        try:
            logger = AuditLogger(log_path=tmp_path)
            entries = logger.read_logs(limit=10)
            assert entries == []
        finally:
            os.unlink(tmp_path)


class TestResolveEnv:
    """${VAR:default} 解析优先级：进程 os.environ 非空值 > .env 非空值 > 默认值"""

    def test_os_environ_nonempty_wins_over_dotenv(self, monkeypatch):
        from mcp_common.config import _resolve_env
        monkeypatch.setenv("PRIO_TEST_VAR", "from_os")
        assert _resolve_env("${PRIO_TEST_VAR:fallback}", {"PRIO_TEST_VAR": "from_dotenv"}) == "from_os"

    def test_dotenv_empty_value_does_not_shadow_os_environ(self, monkeypatch):
        from mcp_common.config import _resolve_env
        monkeypatch.setenv("PRIO_TEST_VAR", "from_os")
        assert _resolve_env("${PRIO_TEST_VAR:fallback}", {"PRIO_TEST_VAR": ""}) == "from_os"

    def test_dotenv_empty_value_falls_back_to_default(self, monkeypatch):
        from mcp_common.config import _resolve_env
        monkeypatch.delenv("PRIO_TEST_VAR", raising=False)
        # .env 中的 "PLCSIM_TARGET_IP="（空值）不得让 ${PLCSIM_TARGET_IP:192.168.0.1} 解析为空串
        assert _resolve_env("${PRIO_TEST_VAR:192.168.0.1}", {"PRIO_TEST_VAR": ""}) == "192.168.0.1"

    def test_os_environ_empty_value_falls_back_to_dotenv(self, monkeypatch):
        from mcp_common.config import _resolve_env
        monkeypatch.setenv("PRIO_TEST_VAR", "")
        assert _resolve_env("${PRIO_TEST_VAR:fallback}", {"PRIO_TEST_VAR": "from_dotenv"}) == "from_dotenv"

    def test_dotenv_nonempty_override_still_works(self, monkeypatch):
        from mcp_common.config import _resolve_env
        monkeypatch.delenv("PRIO_TEST_VAR", raising=False)
        assert _resolve_env("${PRIO_TEST_VAR:fallback}", {"PRIO_TEST_VAR": "from_dotenv"}) == "from_dotenv"

    def test_both_empty_and_no_default_resolves_empty(self, monkeypatch):
        from mcp_common.config import _resolve_env
        monkeypatch.delenv("PRIO_TEST_VAR", raising=False)
        assert _resolve_env("${PRIO_TEST_VAR}", {"PRIO_TEST_VAR": ""}) == ""


class TestTiaWorkerClient:
    """TiaWorker 共享客户端测试"""

    def test_client_not_available(self):
        from mcp_common.tiaworker_client import TiaWorkerClient
        client = TiaWorkerClient(exe_path="nonexistent/TiaWorker.exe")
        assert not client.available

    def test_client_make_error(self):
        from mcp_common.tiaworker_client import make_error, ERR_CODES
        err = make_error("NOT_FOUND", "file missing")
        assert not err["success"]
        assert "TIA_ERR_001" in err["error"]
        assert err["error_code"] == "NOT_FOUND"

    def test_err_codes_complete(self):
        from mcp_common.tiaworker_client import ERR_CODES, ERR_MSGS
        assert len(ERR_CODES) == len(ERR_MSGS)
        for key in ERR_CODES:
            assert key in ERR_MSGS, f"missing message for {key}"
