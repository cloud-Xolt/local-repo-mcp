from dataclasses import dataclass
from typing import Any

PERMISSION_ORDER = ("read", "write", "test", "execute", "ship")

DEFAULT_ROLES: dict[str, list[str]] = {
    "viewer": ["read"],
    "developer": ["read", "write"],
    "tester": ["read", "write", "test", "execute"],
    "shipper": ["read", "write", "test", "execute", "ship"],
}


@dataclass
class RoleDecision:
    allowed: bool
    role: str
    reason: str = ""


class RBACEngine:
    def __init__(self, rules: dict[str, Any]) -> None:
        rbac = rules.get("rbac", {})
        self.default_role = rbac.get("default_role", "developer")
        self.roles: dict[str, list[str]] = {}
        for name, spec in rbac.get("roles", DEFAULT_ROLES).items():
            if isinstance(spec, dict):
                self.roles[name] = list(spec.get("permissions", []))
            else:
                self.roles[name] = list(spec)
        if not self.roles:
            self.roles = dict(DEFAULT_ROLES)
        self.users: dict[str, str] = dict(rbac.get("users", {}))

    def resolve_role(self, user: str) -> str:
        if user in self.users:
            return self.users[user]
        wildcard = self.users.get("*")
        if wildcard:
            return wildcard
        return self.default_role

    def role_permissions(self, role: str) -> list[str]:
        return self.roles.get(role, self.roles.get(self.default_role, ["read"]))

    @staticmethod
    def _perm_level(permission: str) -> int:
        if permission == "execute":
            permission = "test"
        try:
            return PERMISSION_ORDER.index(permission)
        except ValueError:
            return -1

    def role_allows(self, user: str, required: str) -> RoleDecision:
        role = self.resolve_role(user)
        permissions = self.role_permissions(role)
        required_level = self._perm_level(required)
        for perm in permissions:
            if self._perm_level(perm) >= required_level:
                return RoleDecision(True, role)
        return RoleDecision(
            False,
            role,
            f"RBAC denied: user={user} role={role} lacks {required}",
        )

    def require_permission(self, user: str, required: str) -> RoleDecision:
        decision = self.role_allows(user, required)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        return decision
