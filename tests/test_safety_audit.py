import json
import os
import tempfile
import pytest

from mcp_common.audit import AuditLogger


@pytest.fixture
def logger():
    with tempfile.TemporaryDirectory() as tmp:
        yield AuditLogger(os.path.join(tmp, "audit.log"))


def test_audit_creates_log(logger):
    entry = logger.log("test_write", "DB1.Motor", "1500", operator="test")
    assert os.path.exists(str(logger.path))
    assert entry["action"] == "test_write"
    assert entry["target"] == "DB1.Motor"
    assert "hash" in entry
    assert "prev_hash" in entry


def test_audit_chain_is_verifiable(logger):
    logger.log("write_1", "DB1.Motor", "100")
    logger.log("write_2", "DB1.Motor", "200")
    logger.log("write_3", "DB1.Motor", "300")
    assert logger.verify()


def test_audit_chain_detects_tampering():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "audit.log")
        logger = AuditLogger(log_path)

        logger.log("write_1", "DB1.Motor", "100")
        logger.log("write_2", "DB1.Motor", "200")

        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        entries = [json.loads(l) for l in lines]

        entries[0]["value"] = "999"
        with open(log_path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

        assert not logger.verify()


def test_audit_empty_log_is_valid():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "nonexistent.log")
        logger = AuditLogger(log_path)
        assert logger.verify()


def test_audit_zero_byte_log_is_valid():
    """0 字节文件等同于空链（合法零锚起点），必须验证通过。"""
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "audit.log")
        open(log_path, "wb").close()
        logger = AuditLogger(log_path)
        assert logger.verify()


def test_audit_whitespace_only_log_rejected_on_append():
    """非空但全空白的审计文件不得静默回退零锚重起链（截断式篡改绕过）。"""
    from mcp_common.audit import AuditStorageError

    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "audit.log")
        logger = AuditLogger(log_path)
        logger.log("write_1", "DB1.Motor", "100")

        # 模拟"截断旧链 + 空白化"篡改：内容非空但无任何合法条目
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("   \n\n\t\n")

        with pytest.raises(AuditStorageError, match="拒绝静默重锚"):
            logger.log("write_2", "DB1.Motor", "200")


def test_verify_rejects_whitespace_only_log():
    """verify() 对"非空但解析不出任何合法条目"必须返回损坏，而非 True。"""
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "audit.log")
        logger = AuditLogger(log_path)
        logger.log("write_1", "DB1.Motor", "100")

        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n  \n")

        assert not logger.verify()


def test_audit_prev_hash_chains():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "audit.log")
        logger = AuditLogger(log_path)

        e1 = logger.log("a1", "T1", "1")
        e2 = logger.log("a2", "T2", "2")

        assert e2["prev_hash"] == e1["hash"]
        assert e2["hash"] != e1["hash"]


def test_audit_log_optional_fields():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "audit.log")
        logger = AuditLogger(log_path)

        entry = logger.log("read", "DB1.Motor", success=False,
                           detail="connection timeout")
        assert not entry["success"]
        assert entry["detail"] == "connection timeout"


def test_audit_log_default_operator():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "audit.log")
        logger = AuditLogger(log_path)

        entry = logger.log("scan", "DB1.Temp", "25.5")
        assert entry["operator"] == "ai-agent"
