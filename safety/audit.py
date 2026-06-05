import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone


class AuditLogger:
    """不可篡改的审计日志（链式哈希）"""

    def __init__(self, log_path: str = "./logs/audit.log"):
        self.path = Path(log_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        if not self.path.exists():
            return "0" * 64
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    return json.loads(lines[-1]).get("hash", "0" * 64)
        except Exception:
            pass
        return "0" * 64

    def _compute_hash(self, entry: dict, prev_hash: str) -> str:
        payload = json.dumps(entry, sort_keys=True) + prev_hash
        return hashlib.sha256(payload.encode()).hexdigest()

    def log(
        self,
        action: str,
        target: str,
        value: str = "",
        operator: str = "ai-agent",
        success: bool = True,
        detail: str = "",
    ) -> dict:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "target": target,
            "value": str(value),
            "operator": operator,
            "success": success,
            "detail": detail,
        }
        entry["prev_hash"] = self._prev_hash
        entry["hash"] = self._compute_hash(entry, self._prev_hash)

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._prev_hash = entry["hash"]
        return entry

    def verify(self) -> bool:
        """验证日志链是否完整（检测篡改）"""
        if not self.path.exists():
            return True
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            for i, line in enumerate(lines):
                entry = json.loads(line)
                expected = "0" * 64 if i == 0 else json.loads(lines[i - 1])["hash"]
                if entry.get("prev_hash") != expected:
                    return False
                body = {k: v for k, v in entry.items() if k != "hash"}
                if self._compute_hash(body, entry["prev_hash"]) != entry["hash"]:
                    return False
            return True
        except Exception:
            return False


audit = AuditLogger()
