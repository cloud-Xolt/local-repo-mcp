from __future__ import annotations

import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import time
from pathlib import Path


def _gradle_command() -> list[str]:
    return ["gradlew.bat" if os.name == "nt" else "./gradlew", "test"]


TEST_COMMANDS = {
    "python_pytest": [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
    "go_test": ["go", "test", "./..."],
    "node_test": ["npm", "test", "--"],
    "node_lint": ["npm", "run", "lint", "--"],
    "maven_test": ["mvn", "test"],
    "gradle_test": _gradle_command(),
}

_ALLOWED_ENV = {
    "PATH", "HOME", "USER", "USERNAME", "USERPROFILE", "SYSTEMROOT",
    "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
    "LANG", "LC_ALL", "APPDATA", "LOCALAPPDATA",
}


def _env_icase_lookup(env: dict[str, str], target: str) -> str:
    target_upper = target.upper()
    for key, value in env.items():
        if key.upper() == target_upper:
            return value
    return ""


def _expanded_value(value: str) -> str | None:
    expanded = os.path.expandvars(value)
    return None if "%" in expanded else expanded


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
            ("HOME", "home"), ("USERPROFILE", "home"),
            ("APPDATA", "home/AppData/Roaming"),
            ("LOCALAPPDATA", "home/AppData/Local"),
        ):
            if _valid_absolute_path(env.get(key)) is None:
                target = temp_root / Path(suffix)
                target.mkdir(parents=True, exist_ok=True)
                env[key] = str(target)
        if not _expanded_value(_env_icase_lookup(env, "SystemDrive")):
            system_root = _valid_absolute_path(_env_icase_lookup(env, "SystemRoot"))
            drive = system_root.drive if system_root is not None else repo_root.drive
            if drive:
                env["SystemDrive"] = drive
    return env


def _terminate_tree(process: subprocess.Popen, timeout: float = 2.0) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            shell=False,
        )
        if result.returncode != 0 and process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        process.kill()


def _temp_output_path(root: Path, prefix: str) -> Path:
    descriptor, raw_path = tempfile.mkstemp(prefix=prefix, dir=root)
    os.close(descriptor)
    return Path(raw_path)


def _read_bounded(path: Path, max_bytes: int) -> tuple[str, bool]:
    size = path.stat().st_size if path.exists() else 0
    with path.open("rb") as handle:
        raw = handle.read(max_bytes)
    return raw.decode("utf-8", errors="replace"), size > max_bytes


class RepoTestRunner:
    def __init__(self, repo_root: Path, max_output_bytes: int, max_timeout: int) -> None:
        self.repo_root = repo_root
        self.max_output_bytes = max_output_bytes
        self.max_timeout = max_timeout

    def run(self, command_key: str, timeout_seconds: int) -> dict:
        if command_key not in TEST_COMMANDS:
            allowed = ", ".join(sorted(TEST_COMMANDS))
            raise PermissionError(
                f"test command is not allowed: {command_key}; allowed={allowed}"
            )
        timeout = min(max(int(timeout_seconds), 1), self.max_timeout)
        command = TEST_COMMANDS[command_key]
        temp_root = _safe_temp_root(self.repo_root)
        stdout_path = _temp_output_path(temp_root, "stdout-")
        stderr_path = _temp_output_path(temp_root, "stderr-")
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                try:
                    process = subprocess.Popen(
                        command,
                        cwd=self.repo_root,
                        shell=False,
                        stdin=subprocess.DEVNULL,
                        stdout=stdout,
                        stderr=stderr,
                        env=_safe_environment(self.repo_root),
                        creationflags=creationflags,
                        start_new_session=os.name != "nt",
                    )
                except FileNotFoundError as exc:
                    raise FileNotFoundError(
                        f"required test executable was not found: {command[0]}"
                    ) from exc
                deadline = time.monotonic() + timeout
                capture_limit = max(self.max_output_bytes * 4, 1_000_000)
                while process.poll() is None:
                    if time.monotonic() >= deadline:
                        _terminate_tree(process)
                        raise TimeoutError(
                            f"test command exceeded {timeout} seconds and its process tree was terminated"
                        )
                    total_size = stdout_path.stat().st_size + stderr_path.stat().st_size
                    if total_size > capture_limit:
                        _terminate_tree(process)
                        raise PermissionError(
                            f"test output exceeded capture limit: {total_size} > {capture_limit}"
                        )
                    time.sleep(0.05)
                returncode = int(process.returncode or 0)
            stdout_text, stdout_truncated = _read_bounded(
                stdout_path, self.max_output_bytes
            )
            stderr_text, stderr_truncated = _read_bounded(
                stderr_path, self.max_output_bytes
            )
            return {
                "command": " ".join(shlex.quote(part) for part in command),
                "returncode": returncode,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
                "timeout_seconds": timeout,
            }
        finally:
            stdout_path.unlink(missing_ok=True)
            stderr_path.unlink(missing_ok=True)
