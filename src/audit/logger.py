from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any


class AuditLogger:
    """Metadata-only JSONL audit logger."""

    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser().resolve() if path.strip() else None
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.path is not None

    @staticmethod
    def hash_value(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]

    def log(self, **record: Any) -> None:
        if self.path is None:
            return
        payload = {"timestamp": int(time.time()), **record}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            if os.name != "nt":
                try:
                    os.chmod(self.path, 0o600)
                except OSError:
                    pass
