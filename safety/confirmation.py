"""跨进程的一次性人工确认令牌。"""

from __future__ import annotations

import base64
import decimal
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from typing import Any


class ConfirmationError(RuntimeError):
    """确认令牌无法安全用于写入时抛出。"""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _values_equal(left: Any, right: Any) -> bool:
    """确认值比较：int/float/数字字符串按精确数值比较，容忍类型漂移；
    布尔不参与数值比较；其余类型回退到规范序列化严格比较（fail-closed）。"""
    if not isinstance(left, bool) and not isinstance(right, bool):
        try:
            left_number = decimal.Decimal(str(left))
            right_number = decimal.Decimal(str(right))
        except (decimal.InvalidOperation, ValueError):
            pass
        else:
            if left_number.is_finite() and right_number.is_finite():
                return left_number == right_number
    return _canonical(left) == _canonical(right)


# 已消费令牌保留时长：超过该时长的 used 记录会被顺带清理，防止 used 表无限增长。
# 保留期必须大于任何签发 ttl_seconds；后端路由已把 ttl 限制为 1..300 秒。
_USED_TOKEN_RETENTION_SECONDS = 7 * 24 * 3600


class ConfirmationService:
    """签发并原子消费绑定到单次写入的一次性令牌。"""

    def __init__(self, *, secret: str | None = None, store_path: Path | str | None = None):
        self._secret = (secret if secret is not None else os.environ.get("SAFETY_CONFIRMATION_SECRET", "")).encode("utf-8")
        self._store_path = Path(
            store_path
            or os.environ.get("SAFETY_CONFIRMATION_STORE")
            or Path(tempfile.gettempdir()) / "ai-plc-confirmations.sqlite3"
        )
        self._db_lock = threading.Lock()
        self._connection_handle: sqlite3.Connection | None = None

    def _require_secret(self) -> None:
        if not self._secret:
            raise ConfirmationError("未配置确认令牌密钥")

    def _connection(self) -> sqlite3.Connection:
        try:
            if self._connection_handle is None:
                self._store_path.parent.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(
                    self._store_path, timeout=5, isolation_level=None, check_same_thread=False
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS used_confirmation_tokens "
                    "(nonce TEXT PRIMARY KEY, used_at INTEGER NOT NULL)"
                )
                self._connection_handle = connection
            return self._connection_handle
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
        try:
            encoded = base64.urlsafe_b64encode(_canonical(payload).encode("utf-8")).rstrip(b"=")
        except (TypeError, ValueError) as exc:
            raise ConfirmationError("确认令牌载荷不可序列化") from exc
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
        try:
            if not _values_equal(payload.get("value"), value):
                raise ConfirmationError("确认令牌值不匹配")
        except ConfirmationError:
            raise
        except (TypeError, ValueError) as exc:
            raise ConfirmationError("确认令牌值不可序列化") from exc
        if payload.get("device_id") != device_id:
            raise ConfirmationError("确认令牌设备身份不匹配")
        nonce = payload.get("nonce")
        if not isinstance(nonce, str) or not nonce:
            raise ConfirmationError("确认令牌缺少随机标识")

        with self._db_lock:
            connection = self._connection()
            # isolation_level=None 下为 autocommit，必须显式 BEGIN/COMMIT/ROLLBACK
            # 将清理 DELETE 与 nonce INSERT 包裹为同一事务：确保"消费即落库"原子，
            # 崩溃窗口内同一一次性令牌不得被再次消费。
            try:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    connection.execute(
                        "DELETE FROM used_confirmation_tokens WHERE used_at < ?",
                        (int(time.time()) - _USED_TOKEN_RETENTION_SECONDS,),
                    )
                    connection.execute(
                        "INSERT INTO used_confirmation_tokens (nonce, used_at) VALUES (?, ?)",
                        (nonce, int(time.time())),
                    )
                    connection.execute("COMMIT")
                except BaseException:
                    try:
                        connection.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                    raise
            except sqlite3.IntegrityError as exc:
                raise ConfirmationError("确认令牌已使用") from exc
            except sqlite3.Error as exc:
                raise ConfirmationError("确认令牌消费记录不可写") from exc
        return payload
