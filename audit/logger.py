import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

SENSITIVE_KEY_PATTERN = re.compile(r"(token|password|secret|key|credential|authorization)", re.I)
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.)"
)


class AuditLogger:
    def __init__(self, log_path: str) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def hash_input(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    def _redact(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            redacted = {}
            for key, value in obj.items():
                if SENSITIVE_KEY_PATTERN.search(str(key)):
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = self._redact(value)
            return redacted
        if isinstance(obj, list):
            return [self._redact(item) for item in obj]
        if isinstance(obj, str):
            if len(obj) > 500:
                obj = obj[:500] + "…"
            return SENSITIVE_VALUE_PATTERN.sub("[REDACTED]", obj)
        return obj

    def log(
        self,
        tool: str,
        session_id: str,
        payload: dict[str, Any],
        result: str,
        risk_level: str = "low",
        target_files: list[str] | None = None,
        input_hash: str = "",
    ) -> None:
        record = {
            "session_id": session_id or "",
            "tool": tool,
            "timestamp": int(time.time()),
            "input_hash": input_hash,
            "target_files": target_files or [],
            "result": result,
            "risk_level": risk_level,
            "payload": self._redact(payload),
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
