from __future__ import annotations

from pathlib import Path

from conftest import commit_all, init_repo
from repo.file_scope import RepoFileScope, TraversalOptions
from repo.filesystem import RepoFilesystem
from repo.git import git_list_files
from repo.search import search_repository


def _write_repo(root: Path) -> None:
    (root / "src").mkdir()
    (root / "src" / "app.go").write_text("package main\nneedle\n", encoding="utf-8")
    (root / "src" / "keep.go").write_text("package main\nneedle keep\n", encoding="utf-8")
    (root / ".gocache").mkdir()
    (root / ".gocache" / "build.txt").write_text("needle cache\n", encoding="utf-8")
    (root / "coverage").mkdir()
    (root / "coverage" / "out.txt").write_text("needle coverage\n", encoding="utf-8")
    (root / "tmp.log").write_text("needle log\n", encoding="utf-8")
    (root / "big.bin").write_bytes(b"\x00" + b"x" * 128)
    (root / ".gitignore").write_text("*.log\ncoverage/\n", encoding="utf-8")
    (root / ".mcpignore").write_text("src/app.go\n", encoding="utf-8")


def test_git_list_files_honors_exclude_standard(tmp_path: Path) -> None:
    root = init_repo(tmp_path / "repo")
    _write_repo(root)
    commit_all(root)

    tracked = git_list_files(root, respect_gitignore=True)
    assert "src/keep.go" in tracked
    assert "tmp.log" not in tracked
    assert "coverage/out.txt" not in tracked


def test_hard_skip_mcpignore_and_gitignore_apply_to_scope(tmp_path: Path) -> None:
    root = init_repo(tmp_path / "repo")
    _write_repo(root)
    commit_all(root)

    scope = RepoFileScope(root)
    options = TraversalOptions(path=".", limit=200, max_file_bytes=64)
    listed = {path for path, _ in scope.iter_scoped_files(options)}

    assert "src/keep.go" in listed
    assert "src/app.go" not in listed
    assert ".gocache/build.txt" not in listed
    assert "coverage/out.txt" not in listed
    assert "tmp.log" not in listed
    assert "big.bin" not in listed


def test_list_and_search_share_the_same_filter(tmp_path: Path) -> None:
    root = init_repo(tmp_path / "repo")
    (root / "keep.txt").write_text("needle keep\n", encoding="utf-8")
    (root / "skip.txt").write_text("needle skip\n", encoding="utf-8")
    (root / ".gitignore").write_text("skip.txt\n", encoding="utf-8")
    commit_all(root)

    fs = RepoFilesystem(root, max_file_bytes=1000)
    options = TraversalOptions(path=".", limit=200, max_file_bytes=1000)
    listed = set(fs.list_files(options)["files"])
    searched = search_repository(
        "needle",
        root,
        options,
        max_output_bytes=10_000,
        limit=20,
        scope=fs.scope,
    )
    searched_paths = {match["path"] for match in searched["matches"]}

    assert "keep.txt" in listed
    assert "skip.txt" not in listed
    assert searched_paths == {"keep.txt"}
    assert searched_paths <= listed


def test_respect_gitignore_false_includes_gitignored_but_not_hard_skipped(
    tmp_path: Path,
) -> None:
    root = init_repo(tmp_path / "repo")
    (root / "keep.txt").write_text("needle\n", encoding="utf-8")
    (root / "ignored.txt").write_text("needle ignored\n", encoding="utf-8")
    (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (root / ".gocache").mkdir()
    (root / ".gocache" / "cache.txt").write_text("needle cache\n", encoding="utf-8")
    commit_all(root)

    scope = RepoFileScope(root)
    options = TraversalOptions(
        path=".",
        limit=200,
        respect_gitignore=False,
        max_file_bytes=1000,
    )
    paths = {path for path, _ in scope.iter_scoped_files(options)}
    assert "ignored.txt" in paths
    assert ".gocache/cache.txt" not in paths


def test_include_and_exclude_patterns(tmp_path: Path) -> None:
    root = init_repo(tmp_path / "repo")
    (root / "src").mkdir()
    (root / "src" / "a.go").write_text("a\n", encoding="utf-8")
    (root / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    commit_all(root)

    scope = RepoFileScope(root)
    options = TraversalOptions(
        path="src",
        limit=200,
        include=("*.go",),
        exclude=("src/a.go",),
        max_file_bytes=1000,
    )
    paths = {path for path, _ in scope.iter_scoped_files(options)}
    assert paths == set()


def test_binary_and_oversized_files_are_skipped_before_read(tmp_path: Path) -> None:
    root = init_repo(tmp_path / "repo")
    (root / "small.txt").write_text("needle\n", encoding="utf-8")
    (root / "binary.bin").write_bytes(b"\x00needle\n")
    (root / "large.txt").write_text("needle\n" + ("x" * 200), encoding="utf-8")
    commit_all(root)

    fs = RepoFilesystem(root, max_file_bytes=64)
    options = TraversalOptions(path=".", limit=200, max_file_bytes=64)
    listed = set(fs.list_files(options)["files"])
    searched = search_repository(
        "needle",
        root,
        options,
        max_output_bytes=10_000,
        limit=20,
        scope=fs.scope,
    )

    assert listed == {"small.txt"}
    assert {match["path"] for match in searched["matches"]} == {"small.txt"}


def test_walk_fallback_prunes_hard_skip_dirs_without_git(tmp_path: Path) -> None:
    root = tmp_path / "plain"
    root.mkdir()
    (root / "keep.txt").write_text("ok\n", encoding="utf-8")
    (root / ".gocache").mkdir()
    for index in range(200):
        (root / ".gocache" / f"cache-{index}.txt").write_text("x\n", encoding="utf-8")

    scope = RepoFileScope(root)
    options = TraversalOptions(path=".", limit=200, respect_gitignore=False)
    paths = {path for path, _ in scope.iter_scoped_files(options)}
    assert paths == {"keep.txt"}


def test_ripgrep_includes_mcpignore_file(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".mcpignore").write_text("vendor/\n", encoding="utf-8")
    args = RepoFileScope(root).ripgrep_args()
    assert "--ignore-file" in args
    assert str(root / ".mcpignore") in args
