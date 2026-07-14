"""跨进程的一次性人工确认令牌。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any


class ConfirmationError(RuntimeError):
    """确认令牌无法安全用于写入时抛出。"""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ConfirmationService:
    """签发并原子消费绑定到单次写入的一次性令牌。"""

    def __init__(self, *, secret: str | None = None, store_path: Path | str | None = None):
        self._secret = (secret if secret is not None else os.environ.get("SAFETY_CONFIRMATION_SECRET", "")).encode("utf-8")
        self._store_path = Path(
            store_path
            or os.environ.get("SAFETY_CONFIRMATION_STORE")
            or Path(tempfile.gettempdir()) / "ai-plc-confirmations.sqlite3"
        )

    def _require_secret(self) -> None:
        if not self._secret:
            raise ConfirmationError("未配置确认令牌密钥")

    def _connection(self) -> sqlite3.Connection:
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self._store_path, timeout=5, isolation_level=None)
            connection.execute(
                "CREATE TABLE IF NOT EXISTS used_confirmation_tokens "
                "(nonce TEXT PRIMARY KEY, used_at INTEGER NOT NULL)"
            )
            return connection
        except sqlite3.Error as exc:
            raise ConfirmationError("确认令牌消费记录不可写") from exc

    def issue(
        self,
        *,
        operator: str,
        approver: str,
        target: str,
        value: Any,
        device_id: str,
        audit_id: str,
        ttl_seconds: int = 60,
    ) -> str:
        self._require_secret()
        if not approver or approver == operator:
            raise ConfirmationError("确认人必须与操作者不同")
        if not target or not device_id or not audit_id:
            raise ConfirmationError("确认令牌缺少绑定信息")

        now = int(time.time())
        payload = {
            "v": 1,
            "nonce": secrets.token_urlsafe(24),
            "issued_at": now,
            "expires_at": now + ttl_seconds,
            "operator": operator,
            "approver": approver,
            "target": target,
            "value": value,
            "device_id": device_id,
            "audit_id": audit_id,
        }
        encoded = base64.urlsafe_b64encode(_canonical(payload).encode("utf-8")).rstrip(b"=")
        signature = hmac.new(self._secret, encoded, hashlib.sha256).hexdigest()
        return f"{encoded.decode('ascii')}.{signature}"

    def _decode(self, token: str) -> dict[str, Any]:
        self._require_secret()
        try:
            encoded, supplied_signature = token.rsplit(".", 1)
            expected_signature = hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ConfirmationError("确认令牌签名无效")
            padding = "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
        except ConfirmationError:
            raise
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConfirmationError("确认令牌格式无效") from exc
        return payload

    def consume(
        self,
        token: str,
        *,
        operator: str,
        target: str,
        value: Any,
        device_id: str,
    ) -> dict[str, Any]:
        payload = self._decode(token)
        if int(payload.get("expires_at", 0)) < int(time.time()):
            raise ConfirmationError("确认令牌已过期")
        if payload.get("operator") != operator:
            raise ConfirmationError("确认令牌操作者不匹配")
        if payload.get("target") != target:
            raise ConfirmationError("确认令牌目标不匹配")
        if _canonical(payload.get("value")) != _canonical(value):
            raise ConfirmationError("确认令牌值不匹配")
        if payload.get("device_id") != device_id:
            raise ConfirmationError("确认令牌设备身份不匹配")
        nonce = payload.get("nonce")
        if not isinstance(nonce, str) or not nonce:
            raise ConfirmationError("确认令牌缺少随机标识")

        connection = self._connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO used_confirmation_tokens (nonce, used_at) VALUES (?, ?)",
                (nonce, int(time.time())),
            )
            connection.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            connection.execute("ROLLBACK")
            raise ConfirmationError("确认令牌已使用") from exc
        except sqlite3.Error as exc:
            connection.execute("ROLLBACK")
            raise ConfirmationError("确认令牌消费记录不可写") from exc
        finally:
            connection.close()
        return payload
