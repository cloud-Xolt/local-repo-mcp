from __future__ import annotations

import os
import time
from pathlib import Path
from types import TracebackType


class LogFileLock:
    """Small cross-process advisory lock for one JSONL log family."""

    def __init__(self, path: Path, timeout: float = 10.0) -> None:
        self.path = path.with_name(path.name + ".lock")
        self.timeout = timeout
        self._handle = None

    def _try_lock(self) -> bool:
        assert self._handle is not None
        if os.name == "nt":
            import msvcrt

            self._handle.seek(0)
            try:
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                return False

        import fcntl

        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    def __enter__(self) -> "LogFileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+b")
        try:
            self._handle.seek(0, os.SEEK_END)
            if self._handle.tell() == 0:
                self._handle.write(b"0")
                self._handle.flush()
            deadline = time.monotonic() + self.timeout
            while not self._try_lock():
                if time.monotonic() >= deadline:
                    raise TimeoutError("log file lock timed out")
                time.sleep(0.02)
        except BaseException:
            self._handle.close()
            self._handle = None
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            self._handle = None
