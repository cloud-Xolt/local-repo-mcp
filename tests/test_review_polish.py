from __future__ import annotations

import subprocess
from pathlib import Path

from gui.config import AppConfig

ROOT = Path(__file__).resolve().parents[1]


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)


def test_configuration_errors_are_unique(tmp_path: Path) -> None:
    _git_init(tmp_path)
    config = AppConfig(
        repo_root=str(tmp_path),
        transport="streamable-http",
        http_auth_token="token",
        http_tls_terminated_proxy=True,
        http_proxy_trusted_ips="127.0.0.1",
    )
    errors = config.validate()
    assert errors.count("http_public_url_required") == 1
    assert len(errors) == len(set(errors))


def test_mtls_readiness_never_falls_back_to_tcp_only() -> None:
    source = (ROOT / "gui/processes.py").read_text(encoding="utf-8")
    assert "socket.create_connection" not in source
    assert "def restart_http" not in source


def test_primary_actions_disable_while_busy() -> None:
    app_source = (ROOT / "gui/app.py").read_text(encoding="utf-8")
    assert "def _set_busy(self, busy: bool" in app_source
    assert 'fg_color=COLORS["surface_hover"]' in app_source
    assert 'text_color=COLORS["text"]' in app_source
    assert 'busy_label=self.t("starting_tunnel")' in app_source
    i18n = (ROOT / "gui/i18n.py").read_text(encoding="utf-8")
    assert '"starting_tunnel": "正在启动…"' in i18n


def test_systemd_example_matches_wildcard_public_url_requirement() -> None:
    source = (ROOT / "systemd/mcp.env.example").read_text(encoding="utf-8")
    assert "HTTP_HOST=0.0.0.0" in source
    assert "HTTP_PUBLIC_URL=https://mcp.example.com/mcp" in source
    assert "container/pod" in source


def test_package_metadata_uses_readme_and_launcher() -> None:
    source = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'readme = "README.md"' in source
    assert 'local-repo-mcp = "mcp_app.launcher:main"' in source
