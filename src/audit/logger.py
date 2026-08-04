from __future__ import annotations

import hashlib
import sys
import threading
from pathlib import Path
from typing import Any

from audit.event_writer import JsonlEventWriter


class AuditLogger:
    """Stable public interface for audit and runtime JSONL events."""

    def __init__(
        self,
        path: str,
        *,
        max_bytes: int = 5_000_000,
        backup_count: int = 3,
    ) -> None:
        self.path = Path(path).expanduser().resolve() if path.strip() else None
        self.max_bytes = max(64_000, int(max_bytes))
        self.backup_count = max(1, min(int(backup_count), 20))
        self._lock = threading.Lock()
        self._writer = JsonlEventWriter(
            self.path,
            max_bytes=self.max_bytes,
            backup_count=self.backup_count,
            thread_lock=self._lock,
        )

    @property
    def enabled(self) -> bool:
        return self.path is not None

    @staticmethod
    def hash_value(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]

    def log(self, **record: Any) -> None:
        try:
            self._writer.write(record)
        except (OSError, TimeoutError) as exc:
            print(f"Local Repo MCP log write failed: {type(exc).__name__}: {exc}", file=sys.stderr)
