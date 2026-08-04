from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from repo.worktree import initialize_worktree, inspect_worktree, require_worktree_root

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="Git is required")


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args], text=True, encoding="utf-8",
        errors="replace", capture_output=True, check=False, shell=False,
    )


def test_plain_directory_requires_initialization(tmp_path: Path) -> None:
    state = inspect_worktree(tmp_path)
    assert state.status == "not_git"
    assert not state.ready


def test_initialize_directory_creates_unborn_main_without_remote(tmp_path: Path) -> None:
    state = initialize_worktree(tmp_path)
    assert state.ready and state.is_root
    assert state.root == tmp_path.resolve()
    assert state.branch == "main"
    assert (tmp_path / ".git").is_dir()
    assert _git(tmp_path, "rev-parse", "--verify", "HEAD").returncode != 0
    assert _git(tmp_path, "remote").stdout.strip() == ""


def test_existing_repository_is_not_reinitialized(tmp_path: Path) -> None:
    assert _git(tmp_path, "init").returncode == 0
    marker = tmp_path / ".git" / "local-repo-marker"
    marker.write_text("keep", encoding="utf-8")
    state = initialize_worktree(tmp_path)
    assert state.ready and state.is_root
    assert marker.read_text(encoding="utf-8") == "keep"


def test_child_directory_cannot_be_repository_boundary(tmp_path: Path) -> None:
    root = tmp_path / "root"
    child = root / "src" / "feature"
    child.mkdir(parents=True)
    assert _git(root, "init").returncode == 0
    state = inspect_worktree(child)
    assert state.ready and not state.is_root
    assert state.root == root.resolve()
    with pytest.raises(RuntimeError, match="working-tree root"):
        require_worktree_root(child)
    with pytest.raises(RuntimeError, match="existing Git working tree"):
        initialize_worktree(child)


def test_source_gui_entry_uses_final_desktop_application() -> None:
    import run_gui
    from gui.desktop import LocalRepoMCPApp
    assert run_gui.LocalRepoMCPApp is LocalRepoMCPApp
