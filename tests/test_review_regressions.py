from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from gui.config import AppConfig
from gui.config_codec import unprotect_secret
from gui.config_io import read_json_object
from mcp_app.runtime import launcher_command
from repo.lock import RepositoryLock

ROOT = Path(__file__).resolve().parents[1]


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)


def test_gui_uses_single_meaningful_primary_action() -> None:
    source = (ROOT / "gui/app.py").read_text(encoding="utf-8")
    labels = (ROOT / "gui/i18n.py").read_text(encoding="utf-8")
    assert "_save_action" not in source
    assert 'self.t("run_test")' not in source
    assert 'self.t("connect")' in source
    assert 'http_flags.grid(row=8, column=1' in source
    assert "http_flags.grid_configure" not in source
    assert "验证连接" not in labels


def test_installed_layout_uses_packaged_launcher(tmp_path: Path) -> None:
    missing = tmp_path / "missing-launch_mcp.py"
    command = launcher_command(sys.executable, source_launcher=missing)
    assert command[1:] == ["-m", "mcp_app.launcher"]


def test_proxy_wildcard_configuration_is_supported(tmp_path: Path) -> None:
    _git_init(tmp_path)
    config = AppConfig(
        repo_root=str(tmp_path),
        transport="streamable-http",
        http_host="0.0.0.0",
        http_auth_token="x" * 32,
        http_allowed_hosts="example.test",
        http_public_url="https://example.test/mcp",
        http_tls_terminated_proxy=True,
        http_proxy_trusted_ips="10.0.0.0/8",
    )
    assert config.validate() == []


def test_proxy_always_requires_public_url(tmp_path: Path) -> None:
    _git_init(tmp_path)
    config = AppConfig(
        repo_root=str(tmp_path),
        transport="streamable-http",
        http_host="127.0.0.1",
        http_auth_token="x" * 32,
        http_tls_terminated_proxy=True,
        http_proxy_trusted_ips="127.0.0.1",
    )
    assert "http_public_url_required" in config.validate()


def test_public_url_must_match_mcp_path(tmp_path: Path) -> None:
    _git_init(tmp_path)
    config = AppConfig(
        repo_root=str(tmp_path),
        transport="streamable-http",
        http_host="0.0.0.0",
        http_auth_token="x" * 32,
        http_allowed_hosts="example.test",
        http_public_url="https://example.test/wrong",
        http_tls_terminated_proxy=True,
        http_proxy_trusted_ips="10.0.0.0/8",
    )
    assert "http_public_url_invalid" in config.validate()


def test_mtls_gui_connection_requires_client_identity(tmp_path: Path) -> None:
    _git_init(tmp_path)
    cert = tmp_path / "server-cert.pem"
    key = tmp_path / "server-key.pem"
    ca = tmp_path / "client-ca.pem"
    for path in (cert, key, ca):
        path.write_text("test", encoding="utf-8")
    config = AppConfig(
        repo_root=str(tmp_path),
        transport="streamable-http",
        http_auth_token="x" * 32,
        http_tls_certfile=str(cert),
        http_tls_keyfile=str(key),
        http_tls_client_ca=str(ca),
    )
    assert "http_client_cert_required" in config.validate()


def test_non_object_json_is_quarantined(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("[]", encoding="utf-8")
    assert read_json_object(path) == {}
    assert not path.exists()
    assert list(tmp_path.glob("config.invalid.*.json"))


def test_legacy_plaintext_secret_is_migratable() -> None:
    assert unprotect_secret({"http_auth_token": "legacy"}) == "legacy"


def test_repository_lock_uses_git_metadata_and_releases_handle(tmp_path: Path) -> None:
    _git_init(tmp_path)
    lock = RepositoryLock(tmp_path, timeout=1)
    assert lock.path.parent == (tmp_path / ".git").resolve()
    with lock:
        assert lock._handle is not None
    assert lock._handle is None


def test_http_auth_middleware_is_stream_safe() -> None:
    policy = (ROOT / "src/mcp_app/http_policy.py").read_text(encoding="utf-8")
    service = (ROOT / "src/mcp_app/service.py").read_text(encoding="utf-8")
    assert "BaseHTTPMiddleware" not in policy
    assert 'request_path == "/healthz"' in policy
    assert 'host in {"0.0.0.0", "::"}' in service
    assert "HTTP_PUBLIC_URL must be HTTPS" in service
