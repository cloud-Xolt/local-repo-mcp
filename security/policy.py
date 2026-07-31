import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES_PATH = PROJECT_ROOT / "security" / "rules.yaml"

PERMISSION_ORDER = ("read", "write", "test", "execute", "ship")


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str = ""
    risk_level: str = "low"


class PolicyEngine:
    def __init__(self, rules_path: Path | None = None, repo_root: Path | None = None) -> None:
        self.rules_path = rules_path or DEFAULT_RULES_PATH
        self.rules = self._load_rules()
        configured_root = self.rules.get("repo", {}).get("root", ".")
        self.repo_root = (repo_root or PROJECT_ROOT / configured_root).resolve()

    def _load_rules(self) -> dict[str, Any]:
        with self.rules_path.open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def _normalize_rel_path(path: str) -> str:
        return path.replace("\\", "/").strip("/")

    def _match_any(self, rel_path: str, patterns: list[str]) -> bool:
        rel_path = self._normalize_rel_path(rel_path)
        for pattern in patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
            if fnmatch.fnmatch(rel_path.split("/")[-1], pattern):
                return True
        return False

    def _check_permission(self, action: str, rel_path: str) -> PolicyDecision:
        permission = self.rules.get("permission", {}).get(action, {})
        deny = permission.get("deny", [])
        allow = permission.get("allow", ["**"])

        if self._match_any(rel_path, deny):
            return PolicyDecision(False, f"denied by {action} policy: {rel_path}", "high")

        if allow and not self._match_any(rel_path, allow):
            return PolicyDecision(False, f"not in {action} allow list: {rel_path}", "medium")

        return PolicyDecision(True, risk_level="low")

    def check_read(self, rel_path: str) -> PolicyDecision:
        return self._check_permission("read", rel_path)

    def check_write(self, rel_path: str) -> PolicyDecision:
        read_decision = self.check_read(rel_path)
        if not read_decision.allowed:
            return read_decision
        return self._check_permission("write", rel_path)

    def check_execute(self, command_key: str) -> PolicyDecision:
        allowed = self.rules.get("permission", {}).get("execute", {}).get("allow", [])
        if command_key not in allowed:
            return PolicyDecision(False, f"command_key not allowed: {command_key}", "high")
        return PolicyDecision(True, risk_level="medium")

    def protected_branches(self) -> list[str]:
        return self.rules.get("git", {}).get("protected_branches", ["main", "master"])

    def is_protected_branch(self, branch: str) -> bool:
        branch = branch.strip()
        for pattern in self.protected_branches():
            if fnmatch.fnmatch(branch, pattern):
                return True
        return False

    @staticmethod
    def permission_allows(session_permission: str, required: str) -> bool:
        levels = {name: idx for idx, name in enumerate(PERMISSION_ORDER)}
        session_level = levels.get(session_permission, 0)
        required_level = levels.get(required, 0)
        return session_level >= required_level
