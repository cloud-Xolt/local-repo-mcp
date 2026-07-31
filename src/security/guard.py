from __future__ import annotations

import fnmatch
import os
from pathlib import Path

DEFAULT_READ_DENY_PATTERNS: tuple[str, ...] = (
    ".git/**",
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
    ".ssh/**",
    "**/.ssh/**",
    "*.pem",
    "**/*.pem",
    "*.key",
    "**/*.key",
    "*.p12",
    "**/*.p12",
    "*.pfx",
    "**/*.pfx",
    "*id_rsa*",
    "*id_ed25519*",
    "**/credentials/**",
    "**/secrets/**",
)

DEFAULT_WRITE_DENY_PATTERNS: tuple[str, ...] = (
    *DEFAULT_READ_DENY_PATTERNS,
    ".github/workflows/**",
)


def matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/").strip("/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def is_read_denied(path: str) -> bool:
    return matches_any(path, DEFAULT_READ_DENY_PATTERNS)


def is_write_denied(path: str) -> bool:
    return matches_any(path, DEFAULT_WRITE_DENY_PATTERNS)


def resolve_repo_path(repo_root: Path, user_path: str) -> tuple[Path, str]:
    raw = Path(user_path)

    if raw.is_absolute():
        raise PermissionError("absolute paths are not allowed")

    if not user_path or user_path.strip() in {"", "."}:
        raw = Path(".")

    if ".." in raw.parts:
        raise PermissionError("parent traversal is not allowed")

    current = repo_root
    for part in raw.parts:
        current = current / part
        if current.is_symlink():
            raise PermissionError("symbolic links are not allowed")

    resolved = (repo_root / raw).resolve(strict=False)

    try:
        relative = resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise PermissionError("path escapes repository root") from exc

    return resolved, relative.as_posix()


def validate_read_path(repo_root: Path, user_path: str) -> tuple[Path, str]:
    resolved, relative = resolve_repo_path(repo_root, user_path)
    if is_read_denied(relative):
        raise PermissionError(f"read denied: {relative}")
    return resolved, relative


def validate_write_path(repo_root: Path, user_path: str) -> tuple[Path, str]:
    resolved, relative = resolve_repo_path(repo_root, user_path)
    if is_write_denied(relative):
        raise PermissionError(f"write denied: {relative}")
    return resolved, relative


def validate_size_limit(size: int, max_bytes: int, label: str = "file") -> None:
    if size > max_bytes:
        raise PermissionError(f"{label} exceeds limit: {size} > {max_bytes}")


def read_text_file(path: Path, max_bytes: int) -> tuple[str, int]:
    size = path.stat().st_size
    validate_size_limit(size, max_bytes)

    raw = path.read_bytes()

    if b"\x00" in raw[:8192]:
        raise PermissionError("binary files are not supported")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PermissionError("file is not valid UTF-8 text") from exc

    return text, size


def list_files(base: Path, repo_root: Path, limit: int) -> tuple[list[str], bool]:
    limit = min(max(limit, 1), 1000)
    results: list[str] = []

    for root, dirs, files in os.walk(base, followlinks=False):
        root_path = Path(root)

        dirs[:] = [name for name in dirs if not (root_path / name).is_symlink()]

        for name in files:
            item = root_path / name

            if item.is_symlink():
                continue

            relative = item.relative_to(repo_root).as_posix()

            if is_read_denied(relative):
                continue

            results.append(relative)

            if len(results) >= limit:
                return results, True

    return results, False
