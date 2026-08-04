from __future__ import annotations

from pathlib import Path

from conftest import commit_all, init_repo
from repo.controller import GitController
from repo.git import (
    parse_deleted_patch_paths,
    run_git,
)


def controller(repo: Path) -> GitController:
    return GitController(
        repo,
        lambda args, input_text=None, timeout=30: run_git(
            repo,
            args,
            input_text=input_text,
            timeout=timeout,
        ),
        20_000,
    )


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
    patch = (
        "diff --git a/app.py b/app.py\n"
        "index 5626abf..814f4a4 100644\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1,2 @@\n"
        " one\n"
        "+two\n"
    )
    git = controller(repo)
    assert git.patch_targets(patch) == ["app.py"]
    git.apply_patch_check(patch)
    git.apply_patch(patch)
    assert (repo / "app.py").read_text(encoding="utf-8") == "one\ntwo\n"


def test_crlf_patch_protocol_is_normalized(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "app.py").write_text("one\n", encoding="utf-8")
    commit_all(repo)
    patch = (
        "diff --git a/app.py b/app.py\n"
        "index 5626abf..814f4a4 100644\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1,2 @@\n"
        " one\n"
        "+two\n"
    ).replace("\n", "\r\n")
    git = controller(repo)
    git.apply_patch_check(patch)
    git.apply_patch(patch)
    assert (repo / "app.py").read_text(encoding="utf-8") == "one\ntwo\n"


def test_conflicts_are_target_scoped(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    commit_all(repo)
    (repo / "b.txt").write_text("changed\n", encoding="utf-8")

    git = controller(repo)
    assert git.conflicting_paths({"a.txt": "write"}) == []
    assert git.conflicting_paths({"b.txt": "write"}) == ["b.txt"]


def test_untracked_target_can_be_deleted(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "temporary.txt").write_text("temporary\n", encoding="utf-8")
    assert controller(repo).conflicting_paths({"temporary.txt": "delete"}) == []


def test_deleted_patch_path_parser() -> None:
    patch = (
        "diff --git a/a.txt b/a.txt\n"
        "--- a/a.txt\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-a\n"
    )
    assert parse_deleted_patch_paths(patch) == {"a.txt"}
