from pathlib import Path

import pytest

from repo.filesystem import RepoFilesystem


def test_reject_large_file(repo_root: Path) -> None:
    big = repo_root / "src" / "big.txt"
    big.write_text("a" * 300, encoding="utf-8")
    fs = RepoFilesystem(repo_root, max_file_bytes=100)
    with pytest.raises(PermissionError):
        fs.read_file("src/big.txt")


def test_reject_binary_file(repo_root: Path) -> None:
    binary = repo_root / "src" / "bin.dat"
    binary.write_bytes(b"\x00\x01\x02")
    fs = RepoFilesystem(repo_root, max_file_bytes=1000)
    with pytest.raises(PermissionError):
        fs.read_file("src/bin.dat")


def test_reject_non_utf8(repo_root: Path) -> None:
    bad = repo_root / "src" / "bad.txt"
    bad.write_bytes(b"\xff\xfe")
    fs = RepoFilesystem(repo_root, max_file_bytes=1000)
    with pytest.raises(PermissionError):
        fs.read_file("src/bad.txt")


def test_read_returns_raw_content(repo_root: Path) -> None:
    fs = RepoFilesystem(repo_root, max_file_bytes=1000)
    result = fs.read_file("src/app.py")
    assert "print('hello')" in result["content"]
    assert "<untrusted" not in result["content"]
    assert result["content_trust"] == "untrusted_repository_data"


def test_list_files_respects_limit(repo_root: Path) -> None:
    for i in range(5):
        (repo_root / "src" / f"f{i}.py").write_text("x\n", encoding="utf-8")
    fs = RepoFilesystem(repo_root, max_file_bytes=1000)
    result = fs.list_files("src", limit=3)
    assert len(result["files"]) == 3
    assert result["truncated"] is True
