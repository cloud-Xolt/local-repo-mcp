from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from repo.file_scope import RepoFileScope, TraversalOptions
from security.guard import READ_DENY_PATTERNS, validate_read_path

_ARGV_BYTE_BUDGET = 7000


def _ripgrep_supports_files_from() -> bool:
    if not shutil.which("rg"):
        return False
    proc = subprocess.run(
        ["rg", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return "--files-from" in (proc.stdout or "")


def build_ripgrep_command(
    query: str,
    scope: RepoFileScope,
    *,
    paths: list[str] | None = None,
    use_files_from: bool = False,
    max_file_bytes: int | None = None,
) -> list[str]:
    """Build a fixed-string ripgrep command that cannot treat query as an option."""
    command = [
        "rg",
        "--json",
        "--fixed-strings",
        "--line-number",
        "--glob",
        "!.git/**",
    ]
    scoped_paths = paths is not None or use_files_from
    if not scoped_paths:
        command.extend(["--hidden", *scope.ripgrep_args()])
    if use_files_from:
        command.extend(["--files-from", "-"])
    for pattern in READ_DENY_PATTERNS:
        command.extend(["--glob", f"!{pattern}"])
    if max_file_bytes is not None:
        command.extend(["--max-filesize", str(max(max_file_bytes, 1))])
    if scoped_paths and not use_files_from:
        assert paths is not None
        return [*command, "-e", query, "--", *paths]
    return [*command, "-e", query, "--", "."]


def _command_fits_argv(command: list[str]) -> bool:
    return sum(len(part) + 1 for part in command) < _ARGV_BYTE_BUDGET


def _match_payload(payload: dict[str, Any], repo_root: Path) -> dict[str, Any] | None:
    if payload.get("type") != "match":
        return None
    data = payload.get("data", {})
    relative = data.get("path", {}).get("text", "")
    if not relative:
        return None
    try:
        validate_read_path(repo_root, relative)
    except (PermissionError, OSError):
        return None
    return {
        "path": relative.replace("\\", "/"),
        "line": data.get("line_number"),
        "text": data.get("lines", {}).get("text", "")[:500],
    }


def _run_ripgrep_process(
    command: list[str],
    repo_root: Path,
    limit: int,
    max_output_bytes: int,
    timeout_seconds: float,
    stdin_data: str | None = None,
) -> dict[str, Any]:
    process = subprocess.Popen(
        command,
        cwd=repo_root,
        stdin=subprocess.PIPE if stdin_data is not None else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        bufsize=1,
    )
    if stdin_data is not None:
        assert process.stdin is not None
        process.stdin.write(stdin_data)
        process.stdin.close()
    matches: list[dict[str, Any]] = []
    truncated = False
    consumed = 0
    timed_out = False

    def stop_on_timeout() -> None:
        nonlocal timed_out
        timed_out = True
        if process.poll() is None:
            process.kill()

    watchdog = threading.Timer(timeout_seconds, stop_on_timeout)
    watchdog.daemon = True
    watchdog.start()
    assert process.stdout is not None
    try:
        for line in process.stdout:
            consumed += len(line.encode("utf-8", errors="replace"))
            if consumed > max_output_bytes:
                truncated = True
                break
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            match = _match_payload(payload, repo_root)
            if match is None:
                continue
            if len(matches) >= limit:
                truncated = True
                break
            matches.append(match)
    finally:
        watchdog.cancel()
        if process.poll() is None:
            process.terminate()
        try:
            _, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            _, stderr = process.communicate()
    if timed_out:
        raise TimeoutError(f"ripgrep search exceeded {timeout_seconds:g} seconds")
    if process.returncode not in {0, 1, -15, 15} and not truncated:
        raise RuntimeError(stderr.strip() or "ripgrep failed")
    return {"matches": matches, "truncated": truncated, "backend": "ripgrep"}


def _search_with_ripgrep(
    query: str,
    repo_root: Path,
    scope: RepoFileScope,
    options: TraversalOptions,
    limit: int,
    max_output_bytes: int,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    paths = scope.searchable_paths(options)
    if not paths:
        return {"matches": [], "truncated": False, "backend": "ripgrep"}

    if _ripgrep_supports_files_from():
        command = build_ripgrep_command(
            query,
            scope,
            use_files_from=True,
            max_file_bytes=options.max_file_bytes,
        )
        return _run_ripgrep_process(
            command,
            repo_root,
            limit,
            max_output_bytes,
            timeout_seconds,
            stdin_data="\n".join(paths) + "\n",
        )

    command = build_ripgrep_command(
        query,
        scope,
        paths=paths,
        max_file_bytes=options.max_file_bytes,
    )
    if not _command_fits_argv(command):
        raise RuntimeError("scoped ripgrep path list exceeds argv budget")
    return _run_ripgrep_process(
        command,
        repo_root,
        limit,
        max_output_bytes,
        timeout_seconds,
    )


def _search_with_python(
    query: str,
    repo_root: Path,
    scope: RepoFileScope,
    options: TraversalOptions,
    limit: int,
    max_output_bytes: int,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    consumed = 0
    deadline = time.monotonic() + timeout_seconds
    search_options = TraversalOptions(
        path=options.path,
        limit=None,
        include=options.include,
        exclude=options.exclude,
        respect_gitignore=options.respect_gitignore,
        max_file_bytes=options.max_file_bytes,
    )
    for relative, target in scope.iter_scoped_files(search_options):
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Python search exceeded {timeout_seconds:g} seconds")
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(keepends=True), start=1):
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Python search exceeded {timeout_seconds:g} seconds")
            if query not in line:
                continue
            rendered = line[:500]
            consumed += len(rendered.encode("utf-8", errors="replace"))
            if consumed > max_output_bytes or len(matches) >= limit:
                return {"matches": matches, "truncated": True, "backend": "python"}
            matches.append({"path": relative, "line": line_number, "text": rendered})
    return {"matches": matches, "truncated": False, "backend": "python"}


def search_repository(
    query: str,
    repo_root: Path,
    options: TraversalOptions,
    max_output_bytes: int,
    limit: int,
    scope: RepoFileScope | None = None,
) -> dict[str, Any]:
    file_scope = scope or RepoFileScope(repo_root)
    if shutil.which("rg"):
        try:
            return _search_with_ripgrep(
                query,
                repo_root,
                file_scope,
                options,
                limit,
                max_output_bytes,
            )
        except RuntimeError:
            pass
    return _search_with_python(
        query,
        repo_root,
        file_scope,
        options,
        limit,
        max_output_bytes,
    )
