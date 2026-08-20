from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from repo.git import git_list_files, run_git
from security.guard import is_read_denied, is_supported_read_image, max_read_image_bytes, validate_read_path

# Always excluded from MCP traversal/search, even when respect_gitignore=false.
HARD_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".gocache",
        ".cache",
        ".cursor",
        ".venv",
        "venv",
        "node_modules",
        "vendor",
        "dist",
        "build",
        "coverage",
        "htmlcov",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".idea",
        ".vscode",
    }
)

_BINARY_PROBE_BYTES = 8192


@dataclass(frozen=True)
class TraversalOptions:
    path: str = "."
    limit: int | None = 200
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    respect_gitignore: bool = True
    max_file_bytes: int = 200_000


def _normalize_relative(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _has_hard_skip_component(relative: str) -> bool:
    normalized = _normalize_relative(relative)
    if not normalized:
        return False
    return any(part in HARD_SKIP_DIR_NAMES for part in normalized.split("/"))


def _load_glob_patterns(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        return ()
    patterns: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line.replace("\\", "/"))
    return tuple(patterns)


def _matches_glob(relative: str, pattern: str) -> bool:
    path = _normalize_relative(relative)
    glob = _normalize_relative(pattern)
    if not path or not glob:
        return False
    if "**" in glob:
        prefix = glob.split("**", 1)[0].rstrip("/")
        suffix = glob.split("**", 1)[1].lstrip("/")
        if prefix and not path.startswith(prefix + "/") and path != prefix:
            return False
        if suffix:
            return fnmatch.fnmatch(path, f"*{suffix}") or fnmatch.fnmatch(
                path.rsplit("/", 1)[-1],
                suffix,
            )
        return True
    if fnmatch.fnmatch(path, glob):
        return True
    return fnmatch.fnmatch(path.rsplit("/", 1)[-1], glob)


def looks_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return b"\x00" in handle.read(_BINARY_PROBE_BYTES)
    except OSError:
        return True


class RepoFileScope:
    """Shared file scope for repo_list_files and repo_search_code."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self._mcpignore = _load_glob_patterns(self.repo_root / ".mcpignore")

    def ripgrep_args(self) -> list[str]:
        args: list[str] = []
        for name in sorted(HARD_SKIP_DIR_NAMES):
            args.extend(["--glob", f"!**/{name}/**"])
        mcpignore = self.repo_root / ".mcpignore"
        if mcpignore.is_file():
            args.extend(["--ignore-file", str(mcpignore)])
        return args

    def _under_prefix(self, relative: str, prefix: str) -> bool:
        normalized = _normalize_relative(relative)
        scope = _normalize_relative(prefix)
        if not scope or scope == ".":
            return True
        return normalized == scope or normalized.startswith(scope + "/")

    def _matches_include(self, relative: str, include: tuple[str, ...]) -> bool:
        if not include:
            return True
        return any(_matches_glob(relative, pattern) for pattern in include)

    def _matches_exclude(
        self,
        relative: str,
        exclude: tuple[str, ...],
    ) -> bool:
        patterns = (*self._mcpignore, *exclude)
        return any(_matches_glob(relative, pattern) for pattern in patterns)

    def _reject_path(self, relative: str, options: TraversalOptions) -> bool:
        rel = _normalize_relative(relative)
        if not rel:
            return True
        if _has_hard_skip_component(rel):
            return True
        if is_read_denied(rel):
            return True
        if not self._matches_include(rel, options.include):
            return True
        if self._matches_exclude(rel, options.exclude):
            return True
        return False

    def _reject_file(self, relative: str, target: Path, options: TraversalOptions) -> bool:
        if self._reject_path(relative, options):
            return True
        try:
            stat = target.stat()
        except OSError:
            return True
        if stat.st_nlink > 1:
            return True
        if is_supported_read_image(target):
            return stat.st_size > max_read_image_bytes()
        if stat.st_size > options.max_file_bytes:
            return True
        return looks_binary(target)

    def should_prune_dir(self, dir_path: Path) -> bool:
        name = dir_path.name
        if name in HARD_SKIP_DIR_NAMES:
            return True
        try:
            relative = dir_path.relative_to(self.repo_root).as_posix()
        except ValueError:
            return True
        return self._reject_path(relative, TraversalOptions())

    def _git_candidates(self, options: TraversalOptions) -> list[str]:
        prefix = _normalize_relative(options.path) or "."
        try:
            return git_list_files(
                self.repo_root,
                respect_gitignore=options.respect_gitignore,
                path_prefix=prefix,
            )
        except RuntimeError:
            return []

    def _walk_candidates(self, options: TraversalOptions) -> Iterator[str]:
        base, _ = validate_read_path(self.repo_root, options.path or ".")
        if base.is_file():
            yield base.relative_to(self.repo_root).as_posix()
            return
        if not base.is_dir():
            raise FileNotFoundError(options.path)

        for root, dirs, files in os.walk(base, followlinks=False):
            root_path = Path(root)
            dirs[:] = sorted(
                name
                for name in dirs
                if not self.should_prune_dir(root_path / name)
                and not (root_path / name).is_symlink()
            )
            for name in sorted(files):
                candidate = root_path / name
                if candidate.is_symlink():
                    continue
                try:
                    relative = candidate.relative_to(self.repo_root).as_posix()
                    validate_read_path(self.repo_root, relative)
                except (PermissionError, OSError, ValueError):
                    continue
                yield relative

    def iter_scoped_files(self, options: TraversalOptions) -> Iterator[tuple[str, Path]]:
        prefix = _normalize_relative(options.path) or "."
        candidates = self._git_candidates(options)
        if not candidates:
            candidate_iter: Iterator[str] = self._walk_candidates(options)
        else:
            candidate_iter = iter(candidates)

        yielded = 0
        for relative in candidate_iter:
            if options.limit is not None and yielded >= options.limit:
                return
            if not self._under_prefix(relative, prefix):
                continue
            target = self.repo_root / Path(relative)
            if not target.is_file():
                continue
            if self._reject_file(relative, target, options):
                continue
            yielded += 1
            yield relative, target

    def list_files(self, options: TraversalOptions) -> tuple[list[str], bool]:
        files: list[str] = []
        for relative, _ in self.iter_scoped_files(
            TraversalOptions(
                path=options.path,
                limit=options.limit + 1,
                include=options.include,
                exclude=options.exclude,
                respect_gitignore=options.respect_gitignore,
                max_file_bytes=options.max_file_bytes,
            )
        ):
            files.append(relative)
            if len(files) >= options.limit:
                return files, True
        return files, False

    def searchable_paths(self, options: TraversalOptions) -> list[str]:
        return [relative for relative, _ in self.iter_scoped_files(options)]
