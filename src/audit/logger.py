from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, log_path: str) -> None:
        self.enabled = bool(log_path.strip())
        self.log_path = Path(log_path) if self.enabled else None
        if self.enabled and self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                try:
                    os.chmod(self.log_path.parent, 0o700)
                except OSError:
                    pass

    @staticmethod
    def hash_value(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    hash_input = hash_value

    def log(
        self,
        *,
        tool: str,
        status: str,
        target: str | None = None,
        targets: list[str] | None = None,
        input_bytes: int = 0,
        input_hash: str = "",
        result_hash: str = "",
    ) -> None:
        if not self.enabled or self.log_path is None:
            return

        record: dict[str, Any] = {
            "timestamp": int(time.time()),
            "tool": tool,
            "status": status,
            "target": target,
            "targets": targets or [],
            "input_bytes": input_bytes,
            "input_hash": input_hash,
            "result_hash": result_hash,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        if os.name != "nt":
            try:
                os.chmod(self.log_path, 0o600)
            except OSError:
                pass
