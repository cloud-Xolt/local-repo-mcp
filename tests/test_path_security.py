from __future__ import annotations

import os
from pathlib import Path

import pytest

from repo.file_scope import TraversalOptions
from repo.filesystem import RepoFilesystem
from security.guard import validate_read_path, validate_write_path


def test_rejects_absolute_and_parent_paths(tmp_path: Path) -> None:
    with pytest.raises(PermissionError):
        validate_read_path(tmp_path, str(tmp_path / "file.txt"))
    with pytest.raises(PermissionError):
        validate_read_path(tmp_path, "../outside.txt")


def test_rejects_sensitive_paths(tmp_path: Path) -> None:
    for path in (".env", ".git", ".git/config", ".ssh", "id_rsa", "secrets/token.txt"):
        with pytest.raises(PermissionError):
            validate_read_path(tmp_path, path)
    with pytest.raises(PermissionError):
        validate_write_path(tmp_path, ".github/workflows/release.yml")


def test_rejects_symlink(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlink unavailable")
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is not permitted")
    with pytest.raises(PermissionError):
        validate_read_path(tmp_path, "linked.txt")


def test_read_file_rejects_binary_and_non_utf8(tmp_path: Path) -> None:
    fs = RepoFilesystem(tmp_path, 1000)
    (tmp_path / "binary.bin").write_bytes(b"abc\x00def")
    (tmp_path / "bad.txt").write_bytes(b"\xff\xfe")
    (tmp_path / "fake.png").write_bytes(b"not-a-png\x00")
    with pytest.raises(PermissionError):
        fs.read_file("binary.bin")
    with pytest.raises(PermissionError):
        fs.read_file("bad.txt")
    with pytest.raises(PermissionError):
        fs.read_file("fake.png")


def test_list_skips_symlinks_and_sensitive_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=secret", encoding="utf-8")
    fs = RepoFilesystem(tmp_path, 1000)
    result = fs.list_files(TraversalOptions(path=".", limit=200))
    assert "src/app.py" in result["files"]
    assert ".env" not in result["files"]
