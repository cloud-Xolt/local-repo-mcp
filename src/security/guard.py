from __future__ import annotations

import fnmatch
from pathlib import Path

READ_DENY_PATTERNS = (
    ".git",
    ".git/**",
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
    ".ssh",
    ".ssh/**",
    "**/.ssh",
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
    "**/*id_rsa*",
    "*id_ed25519*",
    "**/*id_ed25519*",
    "credentials",
    "credentials/**",
    "**/credentials",
    "**/credentials/**",
    "secrets",
    "secrets/**",
    "**/secrets",
    "**/secrets/**",
)

WRITE_DENY_PATTERNS = (*READ_DENY_PATTERNS, ".github/workflows", ".github/workflows/**")


def _normalize(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    normalized = _normalize(path)
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def is_read_denied(path: str) -> bool:
    return matches_any(path, READ_DENY_PATTERNS)


def is_write_denied(path: str) -> bool:
    return matches_any(path, WRITE_DENY_PATTERNS)


def resolve_repo_path(repo_root: Path, user_path: str) -> tuple[Path, str]:
    root = repo_root.resolve()
    if root.is_symlink():
        raise PermissionError("symbolic links are not allowed")
    raw_text = (user_path or ".").strip()
    raw = Path(raw_text or ".")
    if raw.is_absolute():
        raise PermissionError("absolute paths are not allowed")
    if ".." in raw.parts:
        raise PermissionError("parent traversal is not allowed")

    current = root
    for part in raw.parts:
        if part in {"", "."}:
            continue
        current = current / part
        if current.is_symlink():
            raise PermissionError("symbolic links are not allowed")

    resolved = (root / raw).resolve(strict=False)
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionError("path escapes repository root") from exc
    return resolved, relative.as_posix() or "."


def _reject_hardlinked_file(target: Path) -> None:
    if not target.exists() or not target.is_file():
        return
    try:
        if target.stat().st_nlink > 1:
            raise PermissionError("hard-linked files are not allowed")
    except OSError as exc:
        raise PermissionError("unable to validate file link count") from exc


def validate_read_path(repo_root: Path, user_path: str) -> tuple[Path, str]:
    target, relative = resolve_repo_path(repo_root, user_path)
    if relative != "." and is_read_denied(relative):
        raise PermissionError(f"path is blocked: {relative}")
    _reject_hardlinked_file(target)
    return target, relative


def validate_write_path(repo_root: Path, user_path: str) -> tuple[Path, str]:
    target, relative = resolve_repo_path(repo_root, user_path)
    if relative == "." or is_write_denied(relative):
        raise PermissionError(f"write path is blocked: {relative}")
    _reject_hardlinked_file(target)
    return target, relative


def read_text_file(path: Path, max_bytes: int) -> tuple[str, int]:
    # Re-validate to narrow the TOCTOU window between initial check and read.
    if path.is_symlink():
        raise PermissionError("symbolic links are not allowed")
    size = path.stat().st_size
    if size > max_bytes:
        raise PermissionError(f"file exceeds limit: {size} > {max_bytes}")
    raw = path.read_bytes()
    if b"\x00" in raw[:8192]:
        raise PermissionError("binary files are not supported")
    try:
        return raw.decode("utf-8"), size
    except UnicodeDecodeError as exc:
        raise PermissionError("file is not valid UTF-8 text") from exc
