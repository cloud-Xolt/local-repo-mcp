"""Git branch sandbox — agents must work on agent/* branches only."""

from typing import Callable


def get_current_branch(run_git: Callable) -> str:
    result = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def is_protected_branch(branch: str, protected_patterns: list[str]) -> bool:
    import fnmatch

    branch = branch.strip()
    for pattern in protected_patterns:
        if fnmatch.fnmatch(branch, pattern):
            return True
    return False


def is_agent_branch(branch: str) -> bool:
    return branch.startswith("agent/")


def ensure_agent_branch(session_id: str, run_git: Callable) -> str:
    branch = f"agent/{session_id}"
    exists = run_git(["show-ref", "--verify", f"refs/heads/{branch}"])
    if exists.returncode != 0:
        create = run_git(["checkout", "-b", branch])
        if create.returncode != 0:
            raise RuntimeError(f"failed to create agent branch: {create.stderr}")
    else:
        checkout = run_git(["checkout", branch])
        if checkout.returncode != 0:
            raise RuntimeError(f"failed to checkout agent branch: {checkout.stderr}")
    return branch


def require_writable_branch(run_git: Callable, protected_patterns: list[str]) -> None:
    current = get_current_branch(run_git)
    if is_protected_branch(current, protected_patterns):
        raise PermissionError(
            f"writes blocked on protected branch '{current}'; start a session to switch to agent/*"
        )
    if not is_agent_branch(current):
        raise PermissionError(
            f"writes blocked outside agent/* branch (current: '{current}'); call repo_session_start first"
        )
