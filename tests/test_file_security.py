import tempfile
from pathlib import Path

import pytest
import yaml

from repo.filesystem import RepoFilesystem
from security.policy_engine import PolicyEngine


@pytest.fixture
def policy_file(tmp_path: Path) -> Path:
    rules = {
        "repo": {"root": "."},
        "permission": {
            "read": {
                "allow": ["**"],
                "deny": [".env*", "*.pem", ".ssh/**", ".git/**"],
            },
            "write": {
                "allow": ["**"],
                "deny": [".env*", ".github/workflows/**", ".git/**"],
            },
            "execute": {"allow": ["python_pytest"]},
        },
        "git": {"protected_branches": ["main", "master"]},
    }
    path = tmp_path / "policy.yaml"
    path.write_text(yaml.dump(rules), encoding="utf-8")
    return path


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (tmp_path / ".ssh").mkdir()
    (tmp_path / ".ssh" / "id_rsa").write_text("key\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def filesystem(repo_root: Path, policy_file: Path) -> RepoFilesystem:
    policy = PolicyEngine(policy_file, repo_root)
    return RepoFilesystem(repo_root, policy, max_file_bytes=100_000)


def test_reject_path_traversal(filesystem: RepoFilesystem) -> None:
    with pytest.raises(PermissionError):
        filesystem.resolve_path("../../etc/passwd")


def test_reject_env_file(filesystem: RepoFilesystem) -> None:
    with pytest.raises(PermissionError):
        filesystem.resolve_path(".env")


def test_reject_ssh_key(filesystem: RepoFilesystem) -> None:
    with pytest.raises(PermissionError):
        filesystem.resolve_path(".ssh/id_rsa")


def test_reject_git_config(filesystem: RepoFilesystem) -> None:
    with pytest.raises(PermissionError):
        filesystem.resolve_path(".git/config")


def test_allow_normal_file(filesystem: RepoFilesystem) -> None:
    path = filesystem.resolve_path("src/app.py")
    assert path.name == "app.py"


def test_read_wraps_untrusted(filesystem: RepoFilesystem) -> None:
    result = filesystem.read_file("src/app.py")
    assert "<untrusted_repository_content>" in result["content"]
    assert result["untrusted"] is True


def test_reject_write_to_workflows(filesystem: RepoFilesystem) -> None:
    with pytest.raises(PermissionError):
        filesystem.check_write_path(".github/workflows/ci.yml")
