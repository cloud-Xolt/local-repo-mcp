from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def init_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"],
        check=True,
    )
    return path


def commit_all(path: Path, message: str = "initial") -> None:
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-qm", message],
        check=True,
    )


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    repo = init_repo(tmp_path / "repo")
    source = repo / "src"
    source.mkdir(parents=True)
    (source / "app.py").write_text("print('hello')\n", encoding="utf-8")
    commit_all(repo)

    # Security-diff tests intentionally track this sensitive file in a second
    # commit, so it must exist as an untracked file after the initial commit.
    (repo / ".env").write_text("SECRET=1\n", encoding="utf-8")
    return repo
