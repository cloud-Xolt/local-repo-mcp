from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from types import TracebackType


def _git_common_dir(repo_root: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=10,
        check=False,
        shell=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        common = Path(result.stdout.strip())
        if not common.is_absolute():
            common = repo_root.resolve() / common
        return common.resolve()
    fallback = repo_root.resolve() / ".git"
    if fallback.is_dir():
        return fallback
    return repo_root.resolve()


class RepositoryLock:
    """Cross-process advisory lock stored in shared Git metadata."""

    def __init__(self, repo_root: Path, timeout: float = 30.0) -> None:
        self.path = _git_common_dir(repo_root) / ".local-repo-mcp.lock"
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

    def __enter__(self) -> "RepositoryLock":
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
                    raise TimeoutError("repository mutation lock timed out")
                time.sleep(0.05)
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
