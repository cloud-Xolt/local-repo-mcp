from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repo.controller import GitController
from repo.git import run_git


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        shell=False,
    )


def _controller(path: Path) -> GitController:
    return GitController(
        path,
        lambda args, input_text=None, timeout=30: run_git(
            path,
            args,
            input_text=input_text,
            timeout=timeout,
        ),
        100_000,
    )


def _repo(path: Path) -> None:
    assert _git(path, "init", "-b", "main").returncode == 0
    assert _git(path, "config", "user.email", "tests@example.invalid").returncode == 0
    assert _git(path, "config", "user.name", "Tests").returncode == 0
    (path / "a.txt").write_text("a0\n", encoding="utf-8")
    (path / "b.txt").write_text("b0\n", encoding="utf-8")
    assert _git(path, "add", "a.txt", "b.txt").returncode == 0
    assert _git(path, "commit", "-m", "initial").returncode == 0


def test_multi_file_patch_is_supported_as_one_atomic_operation(tmp_path: Path) -> None:
    _repo(tmp_path)
    patch = """diff --git a/a.txt b/a.txt
--- a/a.txt
+++ b/a.txt
@@ -1 +1 @@
-a0
+a1
diff --git a/b.txt b/b.txt
--- a/b.txt
+++ b/b.txt
@@ -1 +1 @@
-b0
+b1
"""
    controller = _controller(tmp_path)

    assert controller.patch_targets(patch) == ["a.txt", "b.txt"]
    controller.apply_patch_check(patch)
    controller.apply_patch(patch)

    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "a1\n"
    assert (tmp_path / "b.txt").read_text(encoding="utf-8") == "b1\n"


def test_invalid_file_in_multi_patch_leaves_every_target_unchanged(tmp_path: Path) -> None:
    _repo(tmp_path)
    patch = """diff --git a/a.txt b/a.txt
--- a/a.txt
+++ b/a.txt
@@ -1 +1 @@
-a0
+a1
diff --git a/b.txt b/b.txt
--- a/b.txt
+++ b/b.txt
@@ -1 +1 @@
-does-not-match
+b1
"""
    controller = _controller(tmp_path)

    with pytest.raises(RuntimeError):
        controller.apply_patch(patch)

    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "a0\n"
    assert (tmp_path / "b.txt").read_text(encoding="utf-8") == "b0\n"
