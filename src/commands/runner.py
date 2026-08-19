from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from commands.models import CommandBatchResult, CommandResult, CommandSpec, CommandStatus
from commands.preflight import preflight_error
from commands.registry import DEFAULT_COMMAND_REGISTRY, CommandRegistry
from security.guard import validate_read_path

_ALLOWED_ENV = {
    "PATH", "HOME", "USER", "USERNAME", "USERPROFILE", "SYSTEMROOT",
    "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
    "LANG", "LC_ALL", "APPDATA", "LOCALAPPDATA",
}
_ALLOWED_ENV_PREFIXES = (
    "GO",
    "JAVA",
    "MAVEN",
    "GRADLE",
    "NODE",
    "NPM",
    "CGO",
    "CARGO",
    "RUST",
)


def _env_allowed(key: str) -> bool:
    upper = key.upper()
    if upper in _ALLOWED_ENV:
        return True
    return any(upper.startswith(prefix) for prefix in _ALLOWED_ENV_PREFIXES)
_MAX_BATCH_COMMANDS = 8
EventSink = Callable[[dict[str, Any]], None]


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
    resolved_repo = repo_root.resolve()
    candidates: list[Path] = []
    for key in ("TEMP", "TMP"):
        candidate = _valid_absolute_path(os.environ.get(key))
        if candidate is not None:
            candidates.append(candidate / "local-repo-mcp-commands")
    local_appdata = _valid_absolute_path(os.environ.get("LOCALAPPDATA"))
    if local_appdata is not None:
        candidates.append(local_appdata / "Temp" / "local-repo-mcp-commands")
    candidates.append(repo_root.resolve().parent / ".local-repo-mcp-commands")
    for candidate in candidates:
        try:
            resolved_candidate = candidate.resolve(strict=False)
            if resolved_candidate == resolved_repo or resolved_candidate.is_relative_to(
                resolved_repo
            ):
                continue
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate.resolve()
        except OSError:
            continue
    raise RuntimeError("unable to create a safe external command directory")


def _safe_environment(repo_root: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if not _env_allowed(key):
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
    goflags = env.get("GOFLAGS", "").strip()
    if "-buildvcs=false" not in goflags:
        env["GOFLAGS"] = f"{goflags} -buildvcs=false".strip() if goflags else "-buildvcs=false"
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
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            process.kill()
    try:
        process.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    if os.name == "nt":
        process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
    process.wait(timeout=timeout)


def _temp_output_path(root: Path, prefix: str) -> Path:
    descriptor, raw_path = tempfile.mkstemp(prefix=prefix, dir=root)
    os.close(descriptor)
    return Path(raw_path)


def _read_bounded(path: Path, max_bytes: int) -> tuple[str, bool]:
    size = path.stat().st_size if path.exists() else 0
    with path.open("rb") as handle:
        raw = handle.read(max_bytes)
    return raw.decode("utf-8", errors="replace"), size > max_bytes


def _resolve_working_dir(repo_root: Path, working_dir: str) -> tuple[Path, str]:
    target, relative = validate_read_path(repo_root, working_dir or ".")
    if not target.is_dir():
        raise NotADirectoryError(f"working_dir is not a directory: {relative}")
    return target.resolve(), relative


def _preflight_failure(
    spec: CommandSpec,
    *,
    working_dir: Path,
    working_dir_relative: str,
) -> CommandResult | None:
    stderr = preflight_error(spec, working_dir.resolve())
    if not stderr:
        return None

    return CommandResult(
        spec=spec,
        status="failed",
        exit_code=1,
        stdout="",
        stderr=stderr,
        stdout_truncated=False,
        stderr_truncated=False,
        timeout_seconds=0,
        duration_ms=0,
        working_dir=working_dir_relative,
    )


class RepoCommandRunner:
    """Execute only registered repository commands with bounded resources."""

    def __init__(
        self,
        repo_root: Path,
        max_output_bytes: int,
        max_timeout: int,
        *,
        registry: CommandRegistry = DEFAULT_COMMAND_REGISTRY,
        event_sink: EventSink | None = None,
        max_batch_commands: int = _MAX_BATCH_COMMANDS,
    ) -> None:
        if int(max_output_bytes) <= 0:
            raise ValueError("max_output_bytes must be greater than zero")
        if int(max_timeout) <= 0:
            raise ValueError("max_timeout must be greater than zero")
        self.repo_root = repo_root
        self.max_output_bytes = int(max_output_bytes)
        self.max_timeout = int(max_timeout)
        self.registry = registry
        self.event_sink = event_sink
        self.max_batch_commands = max(1, min(int(max_batch_commands), _MAX_BATCH_COMMANDS))

    def _emit(self, **event: Any) -> None:
        if self.event_sink is not None:
            self.event_sink(event)

    def _resolve_batch(self, command_keys: Sequence[str]) -> tuple[CommandSpec, ...]:
        keys = tuple(str(key).strip() for key in command_keys)
        if not keys or any(not key for key in keys):
            raise ValueError("at least one non-empty command key is required")
        if len(keys) > self.max_batch_commands:
            raise PermissionError(
                f"command batch exceeds limit: {len(keys)} > {self.max_batch_commands}"
            )
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate command keys are not allowed in one batch")
        # Resolve the complete batch before executing anything.
        return tuple(self.registry.get(key) for key in keys)

    def run(
        self,
        command_key: str,
        timeout_seconds: int,
        *,
        working_dir: str = ".",
    ) -> CommandResult:
        spec = self.registry.get(str(command_key).strip())
        return self._run_spec(spec, timeout_seconds, working_dir=working_dir)

    def run_many(
        self,
        command_keys: Sequence[str],
        timeout_seconds: int,
        *,
        stop_on_failure: bool = True,
        working_dir: str = ".",
    ) -> CommandBatchResult:
        specs = self._resolve_batch(command_keys)
        results: list[CommandResult] = []
        for spec in specs:
            result = self._run_spec(spec, timeout_seconds, working_dir=working_dir)
            results.append(result)
            if stop_on_failure and not result.success:
                break
        return CommandBatchResult(
            requested=tuple(spec.key for spec in specs),
            results=tuple(results),
            stop_on_failure=bool(stop_on_failure),
        )

    def _run_spec(
        self,
        spec: CommandSpec,
        timeout_seconds: int,
        *,
        working_dir: str = ".",
    ) -> CommandResult:
        cwd, cwd_relative = _resolve_working_dir(self.repo_root, working_dir)
        blocked = _preflight_failure(
            spec,
            working_dir=cwd,
            working_dir_relative=cwd_relative,
        )
        if blocked is not None:
            self._emit(
                event="command_finish",
                status="failed",
                command_key=spec.key,
                command_kind=spec.kind,
                command=spec.display_command(),
                command_status=blocked.status,
                result_code=blocked.exit_code,
                duration_ms=0,
                reason=blocked.stderr,
                repository_root=str(self.repo_root.resolve()),
                working_dir=cwd_relative,
            )
            return blocked

        timeout = min(max(int(timeout_seconds), 1), self.max_timeout)
        started = time.monotonic()
        temp_root = _safe_temp_root(self.repo_root)
        stdout_path = _temp_output_path(temp_root, "stdout-")
        stderr_path = _temp_output_path(temp_root, "stderr-")
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        status: CommandStatus = "failed"
        process: subprocess.Popen | None = None
        capture_limit = max(self.max_output_bytes * 4, 1_000_000)
        try:
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                try:
                    process = subprocess.Popen(
                        list(spec.argv),
                        cwd=cwd,
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
                        f"required command executable was not found: {spec.argv[0]}"
                    ) from exc
                self._emit(
                    event="command_start",
                    status="running",
                    command_key=spec.key,
                    command_kind=spec.kind,
                    command=spec.display_command(),
                    child_process_id=process.pid,
                    repository_root=str(self.repo_root.resolve()),
                    working_dir=cwd_relative,
                )
                deadline = time.monotonic() + timeout
                while process.poll() is None:
                    if time.monotonic() >= deadline:
                        _terminate_tree(process)
                        status = "timeout"
                        break
                    total_size = stdout_path.stat().st_size + stderr_path.stat().st_size
                    if total_size > capture_limit:
                        _terminate_tree(process)
                        status = "output_limit"
                        break
                    time.sleep(0.05)
                if status == "failed":
                    status = "success" if process.returncode == 0 else "failed"

            stdout_text, stdout_truncated = _read_bounded(
                stdout_path, self.max_output_bytes
            )
            stderr_text, stderr_truncated = _read_bounded(
                stderr_path, self.max_output_bytes
            )
            result = CommandResult(
                spec=spec,
                status=status,
                exit_code=process.returncode if process is not None else None,
                stdout=stdout_text,
                stderr=stderr_text,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
                timeout_seconds=timeout,
                duration_ms=int((time.monotonic() - started) * 1000),
                working_dir=cwd_relative,
            )
            self._emit(
                event="command_finish",
                status="success" if result.success else "failed",
                command_key=spec.key,
                command_kind=spec.kind,
                command=spec.display_command(),
                command_status=result.status,
                result_code=result.exit_code,
                duration_ms=result.duration_ms,
                stdout_truncated=result.stdout_truncated,
                stderr_truncated=result.stderr_truncated,
                reason=(result.stderr or result.stdout).strip()[:500] or None,
                repository_root=str(self.repo_root.resolve()),
                working_dir=cwd_relative,
            )
            return result
        finally:
            if process is not None and process.poll() is None:
                _terminate_tree(process)
            stdout_path.unlink(missing_ok=True)
            stderr_path.unlink(missing_ok=True)
