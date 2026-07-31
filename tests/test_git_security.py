from __future__ import annotations

import subprocess
from pathlib import Path

from conftest import commit_all, init_repo
from repo.git import GitController, run_git


def controller(repo: Path) -> GitController:
    return GitController(repo, lambda args, input_text=None, timeout=30: run_git(repo, args, input_text=input_text, timeout=timeout), 20000)


def test_status_and_diff_hide_sensitive_paths(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "app.py").write_text("one\n", encoding="utf-8")
    (repo / ".env").write_text("TOKEN=old\n", encoding="utf-8")
    commit_all(repo)
    (repo / "app.py").write_text("one\ntwo\n", encoding="utf-8")
    (repo / ".env").write_text("TOKEN=new\n", encoding="utf-8")
    git = controller(repo)
    status = git.status_filtered()
    assert [entry["path"] for entry in status["entries"]] == ["app.py"]
    assert status["hidden_entries"] == 1
    diff = git.diff_filtered()
    assert "two" in diff["diff"]
    assert "TOKEN" not in diff["diff"]
    assert diff["hidden_files"] == 1


def test_patch_targets_and_application(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "app.py").write_text("one\n", encoding="utf-8")
    commit_all(repo)
    patch = """diff --git a/app.py b/app.py
index 5626abf..814f4a4 100644
--- a/app.py
+++ b/app.py
@@ -1 +1,2 @@
 one
+two
"""
    git = controller(repo)
    assert git.patch_targets(patch) == ["app.py"]
    git.apply_patch_check(patch)
    git.apply_patch(patch)
    assert (repo / "app.py").read_text(encoding="utf-8") == "one\ntwo\n"
