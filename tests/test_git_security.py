import subprocess

import pytest

from repo import branch as branch_ops


def _run_git(repo: str, args: list[str], input_text: str | None = None):
    cmd = ["git", "-C", repo, "-c", f"safe.directory={repo}"] + args
    return subprocess.run(cmd, input=input_text, text=True, capture_output=True, timeout=30, check=False)


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(str(repo), ["init", "-b", "master"])
    _run_git(str(repo), ["config", "user.email", "test@example.com"])
    _run_git(str(repo), ["config", "user.name", "test"])
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _run_git(str(repo), ["add", "README.md"])
    _run_git(str(repo), ["commit", "-m", "init"])
    return str(repo)


def test_protected_branch_blocks_write(git_repo: str) -> None:
    def run_git(args, input_text=None, timeout=30):
        return _run_git(git_repo, args, input_text)

    with pytest.raises(PermissionError, match="protected branch"):
        branch_ops.require_writable_branch(run_git, ["main", "master"])


def test_non_agent_branch_blocks_write(git_repo: str) -> None:
    def run_git(args, input_text=None, timeout=30):
        return _run_git(git_repo, args, input_text)

    _run_git(git_repo, ["checkout", "-b", "feature/x"])
    with pytest.raises(PermissionError, match="agent/"):
        branch_ops.require_writable_branch(run_git, [])


def test_agent_branch_allows_write(git_repo: str) -> None:
    def run_git(args, input_text=None, timeout=30):
        return _run_git(git_repo, args, input_text)

    branch_ops.ensure_agent_branch("agent-test001", run_git)
    branch_ops.require_writable_branch(run_git, ["main", "master"])
