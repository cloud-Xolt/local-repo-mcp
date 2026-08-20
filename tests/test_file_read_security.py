from pathlib import Path

import pytest

from repo.file_scope import TraversalOptions
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


def test_read_png_image(repo_root: Path) -> None:
    png = repo_root / "src" / "shot.png"
    png.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01"
        b"\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00"
        b"\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDAT"
        b"\x08\xd7c`\x00\x00"
        b"\x00\x02\x00\x01"
        b"\xe2!\xbc3"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    fs = RepoFilesystem(repo_root, max_file_bytes=1000)
    result = fs.read_file("src/shot.png")
    assert result["content_type"] == "image"
    assert result["mime_type"] == "image/png"
    assert result["content_base64"]


def test_list_files_includes_png(repo_root: Path) -> None:
    png = repo_root / "src" / "shot.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    fs = RepoFilesystem(repo_root, max_file_bytes=1000)
    result = fs.list_files(TraversalOptions(path="src", limit=20))
    assert "src/shot.png" in result["files"]


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
    result = fs.list_files(TraversalOptions(path="src", limit=3))
    assert len(result["files"]) == 3
    assert result["truncated"] is True
