from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

TEST_COMMANDS = {
    "gui_smoke": [sys.executable, "run_gui.py", "--smoke"],
    "python_pytest": [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
    "go_test": ["go", "test", "./..."],
    "node_test": ["npm", "test", "--"],
    "node_lint": ["npm", "run", "lint", "--"],
    "maven_test": ["mvn", "test"],
    "gradle_test": ["./gradlew", "test"],
}

_ALLOWED_ENV = {
    "PATH", "HOME", "USER", "USERNAME", "USERPROFILE", "SYSTEMROOT",
    "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
    "LANG", "LC_ALL", "APPDATA", "LOCALAPPDATA",
}


def _env_icase_lookup(env: dict[str, str], target: str) -> str:
    """Case-insensitive lookup for Windows environment variables."""
    target_upper = target.upper()
    for key, value in env.items():
        if key.upper() == target_upper:
            return value
    return ""


def _expanded_value(value: str) -> str | None:
    expanded = os.path.expandvars(value)
    # Reject unresolved Windows-style placeholders on every host. This also
    # makes Linux/macOS CI able to regression-test Windows environment input.
    if "%" in expanded:
        return None
    return expanded


def _valid_absolute_path(value: str | None) -> Path | None:
    if not value:
        return None
    expanded = _expanded_value(value)
    if not expanded:
        return None
    try:
        candidate = Path(expanded).expanduser()
    except RuntimeError:
        return None
    return candidate if candidate.is_absolute() else None


def _safe_temp_root(repo_root: Path) -> Path:
    candidates: list[Path] = []
    for key in ("TEMP", "TMP"):
        candidate = _valid_absolute_path(os.environ.get(key))
        if candidate is not None:
            candidates.append(candidate / "local-repo-mcp-tests")
    local_appdata = _valid_absolute_path(os.environ.get("LOCALAPPDATA"))
    if local_appdata is not None:
        candidates.append(local_appdata / "Temp" / "local-repo-mcp-tests")
    candidates.append(repo_root.resolve().parent / ".local-repo-mcp-tests")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate.resolve()
        except OSError:
            continue
    raise RuntimeError("unable to create a safe external test directory")


def _safe_environment(repo_root: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key.upper() not in _ALLOWED_ENV:
            continue
        expanded = _expanded_value(value)
        if expanded is not None:
            env[key] = expanded

    temp_root = _safe_temp_root(repo_root)
    env["TEMP"] = str(temp_root)
    env["TMP"] = str(temp_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(temp_root / "pycache")
    env.pop("PYTEST_ADDOPTS", None)

    if os.name == "nt":
        for key, suffix in (
            ("HOME", "home"),
            ("USERPROFILE", "home"),
            ("APPDATA", "home/AppData/Roaming"),
            ("LOCALAPPDATA", "home/AppData/Local"),
        ):
            if _valid_absolute_path(env.get(key)) is None:
                target = temp_root / Path(suffix)
                target.mkdir(parents=True, exist_ok=True)
                env[key] = str(target)

        system_drive_value = _expanded_value(
            _env_icase_lookup(env, "SystemDrive")
        )
        if not system_drive_value:
            system_root = _valid_absolute_path(
                _env_icase_lookup(env, "SystemRoot")
            )
            drive = system_root.drive if system_root is not None else repo_root.drive
            if drive:
                env["SystemDrive"] = drive

    return env


def _truncate(value: str, max_bytes: int) -> tuple[str, bool]:
    raw = value.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return value, False
    return raw[:max_bytes].decode("utf-8", errors="replace"), True


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
        try:
            result = subprocess.run(
                command,
                cwd=self.repo_root,
                shell=False,
                timeout=timeout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_safe_environment(self.repo_root),
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
