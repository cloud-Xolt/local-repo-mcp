from __future__ import annotations

import os
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

MAX_TEST_OUTPUT_BYTES = 20_480
DEFAULT_TIMEOUT = 120
MAX_TIMEOUT = 300


def truncate_text(value: str, max_bytes: int) -> tuple[str, bool]:
    raw = value.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return value, False
    clipped = raw[-max_bytes:].decode("utf-8", errors="replace")
    return clipped, True


def build_safe_environment() -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key.upper().endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD")):
            env.pop(key, None)
    return env


class RepoTestRunner:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def run(self, command_key: str, timeout_seconds: int) -> dict:
        if command_key not in TEST_COMMANDS:
            raise PermissionError(f"unsupported command_key: {command_key}")

        effective_timeout = min(max(timeout_seconds, 1), MAX_TIMEOUT)
        command = TEST_COMMANDS[command_key]

        result = subprocess.run(
            command,
            cwd=self.repo_root,
            shell=False,
            timeout=effective_timeout,
            capture_output=True,
            text=True,
            env=build_safe_environment(),
            check=False,
        )

        stdout, stdout_truncated = truncate_text(result.stdout, MAX_TEST_OUTPUT_BYTES)
        stderr, stderr_truncated = truncate_text(result.stderr, MAX_TEST_OUTPUT_BYTES)

        return {
            "command_key": command_key,
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "timeout_seconds": effective_timeout,
        }
