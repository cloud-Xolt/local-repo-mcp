from pathlib import Path
from typing import Callable

from repo import branch as branch_ops
from repo.patch import PatchValidator
from security.policy_engine import PolicyEngine


class GitController:
    def __init__(self, repo_root: Path, policy: PolicyEngine, run_git: Callable) -> None:
        self.repo_root = repo_root
        self.policy = policy
        self.run_git = run_git
        self.patch_validator = PatchValidator(run_git)

    def current_branch(self) -> str:
        return branch_ops.get_current_branch(self.run_git)

    def ensure_agent_branch(self, session_id: str) -> str:
        return branch_ops.ensure_agent_branch(session_id, self.run_git)

    def require_writable_branch(self) -> None:
        branch_ops.require_writable_branch(self.run_git, self.policy.protected_branches())

    def patch_targets(self, patch: str) -> list[str]:
        return self.patch_validator.targets_from_git_stat(patch)

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
