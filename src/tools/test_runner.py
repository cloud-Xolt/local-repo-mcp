from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

TEST_COMMANDS = {
    "python_pytest": [sys.executable, "-m", "pytest", "-q"],
    "go_test": ["go", "test", "./..."],
    "node_test": ["npm", "test", "--"],
    "node_lint": ["npm", "run", "lint", "--"],
    "maven_test": ["mvn", "test"],
    "gradle_test": ["./gradlew", "test"],
}


def _truncate(value: str, max_bytes: int) -> tuple[str, bool]:
    raw = value.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return value, False
    return raw[-max_bytes:].decode("utf-8", errors="replace"), True


class RepoTestRunner:
    def __init__(self, repo_root: Path, max_output_bytes: int, max_timeout: int) -> None:
        self.repo_root = repo_root
        self.max_output_bytes = max_output_bytes
        self.max_timeout = max_timeout

    def run(self, command_key: str, timeout_seconds: int) -> dict:
        if command_key not in TEST_COMMANDS:
            raise PermissionError(f"test command is not allowed: {command_key}")
        timeout = min(max(int(timeout_seconds), 1), self.max_timeout)
        command = TEST_COMMANDS[command_key]
        env = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "HOME", "USER", "USERNAME", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "LANG", "LC_ALL", "APPDATA", "LOCALAPPDATA"}
        }
        try:
            result = subprocess.run(
                command,
                cwd=self.repo_root,
                shell=False,
                timeout=timeout,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            stdout, stdout_truncated = _truncate(result.stdout, self.max_output_bytes)
            stderr, stderr_truncated = _truncate(result.stderr, self.max_output_bytes)
            return {
                "command": " ".join(shlex.quote(part) for part in command),
                "returncode": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
                "timeout_seconds": timeout,
            }
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"test command exceeded {timeout} seconds") from exc
