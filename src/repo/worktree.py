from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorktreeInfo:
    status: str
    path: Path
    root: Path | None = None
    branch: str = ""
    detail: str = ""

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    @property
    def is_root(self) -> bool:
        return self.ready and self.root is not None and self.path.resolve() == self.root.resolve()


def _run_git(path: Path, *args: str, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), "-c", f"safe.directory={path.resolve()}", *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
        shell=False,
    )


def branch_name(path: Path) -> str:
    """Return a useful label for normal, unborn, and detached HEAD states."""
    symbolic = _run_git(path, "symbolic-ref", "--quiet", "--short", "HEAD")
    if symbolic.returncode == 0 and symbolic.stdout.strip():
        return symbolic.stdout.strip()
    detached = _run_git(path, "rev-parse", "--short", "HEAD")
    if detached.returncode == 0 and detached.stdout.strip():
        return f"detached@{detached.stdout.strip()}"
    return "-"


def inspect_worktree(path: str | Path) -> WorktreeInfo:
    try:
        candidate = Path(path).expanduser()
    except RuntimeError as exc:
        return WorktreeInfo("error", Path(str(path)), detail=str(exc))
    if not candidate.exists():
        return WorktreeInfo("missing", candidate)
    if not candidate.is_dir():
        return WorktreeInfo("not_directory", candidate)

    try:
        result = _run_git(candidate, "rev-parse", "--show-toplevel", timeout=5)
    except FileNotFoundError:
        return WorktreeInfo("git_missing", candidate)
    except OSError as exc:
        return WorktreeInfo("error", candidate, detail=str(exc))
    except subprocess.TimeoutExpired:
        return WorktreeInfo("error", candidate, detail="Git repository check timed out")

    if result.returncode != 0 or not result.stdout.strip():
        detail = (result.stderr or result.stdout).strip()
        status = "not_git" if result.returncode == 128 else "error"
        return WorktreeInfo(status, candidate, detail=detail or "Git repository check failed")

    root = Path(result.stdout.strip()).expanduser().resolve()
    try:
        branch = branch_name(root)
    except (OSError, subprocess.TimeoutExpired):
        branch = "-"
    return WorktreeInfo("ready", candidate.resolve(), root=root, branch=branch)


def require_worktree_root(path: str | Path) -> WorktreeInfo:
    info = inspect_worktree(path)
    if info.status == "git_missing":
        raise RuntimeError("Git is required but was not found")
    if not info.ready or info.root is None:
        raise RuntimeError(info.detail or f"not a Git working tree: {info.path}")
    if not info.is_root:
        raise RuntimeError(
            "repository path must be the Git working-tree root; "
            f"selected={info.path}, root={info.root}"
        )
    return info


def initialize_worktree(path: str | Path) -> WorktreeInfo:
    before = inspect_worktree(path)
    if before.ready:
        if before.is_root:
            return before
        raise RuntimeError(
            "selected directory is inside an existing Git working tree; "
            f"use {before.root}"
        )
    if before.status != "not_git":
        raise RuntimeError(before.detail or before.status)

    try:
        result = _run_git(before.path, "init", "-b", "main", timeout=15)
        if result.returncode != 0:
            result = _run_git(before.path, "init", timeout=15)
    except FileNotFoundError as exc:
        raise RuntimeError("Git was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Git initialization timed out") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail or "Git initialization failed")
    return require_worktree_root(before.path)
