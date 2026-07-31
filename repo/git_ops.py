import subprocess
from pathlib import Path
from typing import Callable

from security.policy import PolicyEngine


class GitController:
    def __init__(self, repo_root: Path, policy: PolicyEngine, run_git: Callable) -> None:
        self.repo_root = repo_root
        self.policy = policy
        self.run_git = run_git

    def current_branch(self) -> str:
        result = self.run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        return result.stdout.strip()

    def ensure_agent_branch(self, session_id: str) -> str:
        current = self.current_branch()
        if not self.policy.is_protected_branch(current):
            return current

        branch = f"agent/{session_id}"
        exists = self.run_git(["show-ref", "--verify", f"refs/heads/{branch}"])
        if exists.returncode != 0:
            create = self.run_git(["checkout", "-b", branch])
            if create.returncode != 0:
                raise RuntimeError(f"failed to create agent branch: {create.stderr}")
        else:
            checkout = self.run_git(["checkout", branch])
            if checkout.returncode != 0:
                raise RuntimeError(f"failed to checkout agent branch: {checkout.stderr}")
        return branch

    def require_writable_branch(self) -> None:
        current = self.current_branch()
        if self.policy.is_protected_branch(current):
            raise PermissionError(
                f"writes blocked on protected branch '{current}'; start a session to create agent/* branch"
            )

    def status_short(self) -> str:
        result = self.run_git(["status", "--short"])
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        return result.stdout

    def diff(self, staged: bool = False) -> str:
        args = ["diff", "--cached"] if staged else ["diff"]
        result = self.run_git(args, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        return result.stdout

    def apply_patch_check(self, patch: str) -> None:
        result = self.run_git(["apply", "--check", "--whitespace=nowarn"], input_text=patch, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"git apply --check failed:\n{result.stderr}")

    def apply_patch(self, patch: str) -> None:
        result = self.run_git(["apply", "--whitespace=nowarn"], input_text=patch, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"git apply failed:\n{result.stderr}")
