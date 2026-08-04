from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audit.file_lock import LogFileLock


def _level(record: dict[str, Any]) -> str:
    explicit = str(record.get("level", "")).strip().upper()
    if explicit in {"DEBUG", "INFO", "WARN", "ERROR", "SECURITY"}:
        return explicit
    status = str(record.get("status", "success")).strip().lower()
    if status == "denied":
        return "SECURITY"
    if status in {"failed", "error"}:
        return "ERROR"
    if status in {"warning", "warn"}:
        return "WARN"
    return "INFO"


def _source(record: dict[str, Any]) -> str:
    explicit = str(record.get("source", "")).strip().lower()
    if explicit:
        return explicit
    event = str(record.get("event", "")).lower()
    if event.startswith("http_"):
        return "http"
    if event.startswith("tunnel_"):
        return "tunnel"
    return "mcp"


def build_event(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    now = time.time()
    timestamp = record.pop("timestamp", now)
    try:
        numeric_timestamp = float(timestamp)
    except (TypeError, ValueError):
        numeric_timestamp = now
    action = str(
        record.get("action")
        or record.get("tool")
        or record.get("event")
        or "event"
    )
    return {
        "schema_version": 1,
        "event_id": f"evt_{time.time_ns():x}_{os.getpid():x}",
        "timestamp": numeric_timestamp,
        "timestamp_ms": int(numeric_timestamp * 1000),
        "timestamp_iso": datetime.fromtimestamp(
            numeric_timestamp, tz=timezone.utc
        ).astimezone().isoformat(timespec="milliseconds"),
        "level": _level(record),
        "source": _source(record),
        "category": str(
            record.get("category")
            or ("tool" if record.get("tool") else "runtime")
        ),
        "action": action,
        "status": str(record.get("status", "success")),
        **record,
    }


class JsonlEventWriter:
    def __init__(
        self,
        path: Path | None,
        *,
        max_bytes: int,
        backup_count: int,
        thread_lock: threading.Lock,
    ) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.thread_lock = thread_lock

    def _rotate(self, incoming_bytes: int) -> None:
        assert self.path is not None
        try:
            current_size = self.path.stat().st_size
        except FileNotFoundError:
            return
        if current_size + incoming_bytes <= self.max_bytes:
            return
        oldest = self.path.with_name(f"{self.path.name}.{self.backup_count}")
        oldest.unlink(missing_ok=True)
        for index in range(self.backup_count - 1, 0, -1):
            source = self.path.with_name(f"{self.path.name}.{index}")
            destination = self.path.with_name(f"{self.path.name}.{index + 1}")
            if source.exists():
                os.replace(source, destination)
        if self.path.exists():
            os.replace(self.path, self.path.with_name(f"{self.path.name}.1"))

    @staticmethod
    def _write_all(descriptor: int, encoded: bytes) -> None:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise OSError("incomplete JSONL log write")
            offset += written

    def write(self, record: dict[str, Any]) -> None:
        if self.path is None:
            return
        encoded = (
            json.dumps(build_event(record), ensure_ascii=False, sort_keys=True) + "\n"
        ).encode("utf-8", errors="replace")
        with self.thread_lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with LogFileLock(self.path):
                self._rotate(len(encoded))
                flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
                if hasattr(os, "O_BINARY"):
                    flags |= os.O_BINARY
                descriptor = os.open(self.path, flags, 0o600)
                try:
                    self._write_all(descriptor, encoded)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            if os.name != "nt":
                try:
                    os.chmod(self.path, 0o600)
                except OSError:
                    pass
