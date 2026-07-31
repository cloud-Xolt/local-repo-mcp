import pytest

from security.rbac import RBACEngine


@pytest.fixture
def rbac() -> RBACEngine:
    rules = {
        "rbac": {
            "default_role": "developer",
            "roles": {
                "viewer": {"permissions": ["read"]},
                "developer": {"permissions": ["read", "write"]},
                "tester": {"permissions": ["read", "write", "test", "execute"]},
                "shipper": {"permissions": ["read", "write", "test", "execute", "ship"]},
            },
            "users": {
                "guest": "viewer",
                "dev01": "developer",
                "qa01": "tester",
                "admin": "shipper",
            },
        }
    }
    return RBACEngine(rules)


def test_viewer_can_read(rbac: RBACEngine) -> None:
    assert rbac.role_allows("guest", "read").allowed


def test_viewer_cannot_write(rbac: RBACEngine) -> None:
    assert not rbac.role_allows("guest", "write").allowed


def test_developer_can_write(rbac: RBACEngine) -> None:
    assert rbac.role_allows("dev01", "write").allowed


def test_tester_can_run_test(rbac: RBACEngine) -> None:
    assert rbac.role_allows("qa01", "test").allowed


def test_require_permission_raises(rbac: RBACEngine) -> None:
    with pytest.raises(PermissionError, match="RBAC denied"):
        rbac.require_permission("guest", "write")


def test_default_role_for_unknown_user(rbac: RBACEngine) -> None:
    decision = rbac.role_allows("unknown-user", "write")
    assert decision.allowed
    assert decision.role == "developer"
