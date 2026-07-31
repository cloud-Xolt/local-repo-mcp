import os
from pathlib import Path

import pytest

from security.guard import resolve_repo_path, validate_read_path, validate_write_path


def test_reject_parent_traversal(repo_root: Path) -> None:
    with pytest.raises(PermissionError):
        resolve_repo_path(repo_root, "../../etc/passwd")


def test_reject_absolute_path(repo_root: Path) -> None:
    with pytest.raises(PermissionError):
        resolve_repo_path(repo_root, "/etc/passwd")
    if os.name == "nt":
        with pytest.raises(PermissionError):
            resolve_repo_path(repo_root, r"C:\Windows\System32\config")


def test_reject_env_and_git(repo_root: Path) -> None:
    with pytest.raises(PermissionError):
        validate_read_path(repo_root, ".env")
    with pytest.raises(PermissionError):
        validate_read_path(repo_root, ".git/config")


def test_allow_normal_source(repo_root: Path) -> None:
    _, rel = validate_read_path(repo_root, "src/app.py")
    assert rel == "src/app.py"


def test_reject_external_symlink(repo_root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    link = repo_root / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation requires elevated privileges on this platform")
    with pytest.raises(PermissionError):
        validate_read_path(repo_root, "link.txt")


def test_reject_internal_file_symlink(repo_root: Path) -> None:
    target = repo_root / "src" / "app.py"
    link = repo_root / "src" / "link.py"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation requires elevated privileges on this platform")
    with pytest.raises(PermissionError):
        validate_read_path(repo_root, "src/link.py")


def test_write_deny_workflows(repo_root: Path) -> None:
    with pytest.raises(PermissionError):
        validate_write_path(repo_root, ".github/workflows/ci.yml")
