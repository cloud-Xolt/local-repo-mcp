from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from security.guard import READ_DENY_PATTERNS, SKIP_DIRECTORIES, validate_read_path


def build_ripgrep_command(
    query: str,
    max_file_bytes: int | None = None,
) -> list[str]:
    """Build a fixed-string ripgrep command that cannot treat query as an option."""
    command = [
        "rg", "--json", "--fixed-strings", "--line-number", "--hidden",
        "--glob", "!.git/**", "--glob", "!node_modules/**",
        "--glob", "!vendor/**", "--glob", "!.venv/**",
    ]
    for pattern in READ_DENY_PATTERNS:
        command.extend(["--glob", f"!{pattern}"])
    if max_file_bytes is not None:
        command.extend(["--max-filesize", str(max(max_file_bytes, 1))])
    return [*command, "-e", query, "--", "."]


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


def _search_with_ripgrep(
    query: str,
    repo_root: Path,
    limit: int,
    max_output_bytes: int,
    max_file_bytes: int,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    process = subprocess.Popen(
        build_ripgrep_command(query, max_file_bytes),
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        bufsize=1,
    )
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


def _search_with_python(
    query: str,
    repo_root: Path,
    limit: int,
    max_output_bytes: int,
    max_file_bytes: int,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    consumed = 0
    deadline = time.monotonic() + timeout_seconds
    for root, dirs, files in os.walk(repo_root, followlinks=False):
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Python search exceeded {timeout_seconds:g} seconds")
        root_path = Path(root)
        dirs[:] = [
            name for name in dirs
            if name not in SKIP_DIRECTORIES and not (root_path / name).is_symlink()
        ]
        for name in files:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Python search exceeded {timeout_seconds:g} seconds")
            candidate = root_path / name
            if candidate.is_symlink():
                continue
            relative = candidate.relative_to(repo_root).as_posix()
            try:
                target, _ = validate_read_path(repo_root, relative)
                stat = target.stat()
            except (PermissionError, OSError):
                continue
            if not target.is_file() or stat.st_size > max_file_bytes:
                continue
            try:
                raw = target.read_bytes()
            except OSError:
                continue
            if b"\x00" in raw[:8192]:
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
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
    limit: int,
    max_output_bytes: int,
    max_file_bytes: int,
) -> dict[str, Any]:
    if shutil.which("rg"):
        return _search_with_ripgrep(
            query, repo_root, limit, max_output_bytes, max_file_bytes
        )
    return _search_with_python(
        query, repo_root, limit, max_output_bytes, max_file_bytes
    )
