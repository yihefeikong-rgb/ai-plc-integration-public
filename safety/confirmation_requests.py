"""人工审批请求存储：AI 工作流发起 → 人工审批 → 签发一次性工作流确认令牌。

backend（审批界面）与 orchestrator（编排层工作流）通过同一 JSON 文件共享请求队列，
避免进程间 HTTP 耦合。approve 时调用 ConfirmationService 签发一次性工作流级令牌，
AI 凭 request_id 一次性领取（take_token）后在编排层真实消费。
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from safety.confirmation import ConfirmationError, ConfirmationService

_logger = logging.getLogger(__name__)


class ConfirmationRequestStore:
    """持久化"待人工审批的确认请求"队列（JSON 文件 + 进程内线程锁）。"""

    def __init__(self, path: str | Path | None = None, service: ConfirmationService | None = None):
        self._path = Path(path or os.environ.get(
            "CONFIRMATION_REQUESTS_FILE", "data/confirmation_requests.json"))
        self._service = service if service is not None else ConfirmationService()
        self._lock = threading.Lock()
        self._requests: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._requests = data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            self._requests = {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._requests, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as exc:
            _logger.error("确认请求存储写入失败: %s", exc)

    def create(self, workflow_name: str, description: str = "", operator: str = "ai-agent") -> dict[str, Any]:
        """AI 工作流创建审批请求，返回待人工批准的记录（不含令牌）。"""
        with self._lock:
            request_id = f"req-{int(time.time())}-{secrets.token_hex(3)}"
            record = {
                "request_id": request_id,
                "workflow_name": workflow_name,
                "description": (description or "")[:200],
                "operator": operator,
                "status": "pending",  # pending | approved | denied
                "created_at": int(time.time()),
                "approver": "",
                "token": "",
            }
            self._requests[request_id] = record
            self._save()
            return dict(record)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            items = [dict(r) for r in self._requests.values()]
        # 未决在前，最新在前
        items.sort(key=lambda r: (r["status"] != "pending", -r["created_at"]))
        return items

    def get(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._requests.get(request_id)
            return dict(record) if record else None

    def approve(self, request_id: str, approver: str) -> dict[str, Any]:
        """人工批准：签发一次性工作流级确认令牌并绑定到请求记录。"""
        with self._lock:
            record = self._requests.get(request_id)
            if record is None:
                raise KeyError(f"确认请求不存在: {request_id}")
            if record["status"] != "pending":
                raise ValueError(f"确认请求已处理（当前状态: {record['status']}）")
            workflow_name = record["workflow_name"]
            try:
                token = self._service.issue(
                    operator=f"wf:{workflow_name}",
                    approver=approver,
                    target=f"_wf.{workflow_name}",
                    value="run",
                    device_id="workflow",
                    audit_id=f"wf-confirm:{workflow_name}:{request_id}",
                    ttl_seconds=300,
                )
            except ConfirmationError as exc:
                raise RuntimeError(f"签发确认令牌失败: {exc}") from exc
            record["status"] = "approved"
            record["approver"] = approver
            record["token"] = token
            self._save()
            return {"request_id": request_id, "status": "approved", "confirmation_token": token}

    def deny(self, request_id: str, approver: str) -> dict[str, Any]:
        with self._lock:
            record = self._requests.get(request_id)
            if record is None:
                raise KeyError(f"确认请求不存在: {request_id}")
            if record["status"] != "pending":
                raise ValueError(f"确认请求已处理（当前状态: {record['status']}）")
            record["status"] = "denied"
            record["approver"] = approver
            self._save()
            return {"request_id": request_id, "status": "denied"}

    def take_token(self, request_id: str) -> str | None:
        """AI 凭 request_id 领取已批准令牌（一次性取出后清空，防止复用）。"""
        with self._lock:
            record = self._requests.get(request_id)
            if record is None or record["status"] != "approved" or not record.get("token"):
                return None
            token = record["token"]
            record["token"] = ""  # 一次性领取
            self._save()
            return token


_confirmation_request_store = ConfirmationRequestStore()
