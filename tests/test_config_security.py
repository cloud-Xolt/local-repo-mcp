from __future__ import annotations

import json
from pathlib import Path

import gui.config as config_module
from gui.config import AppConfig


def test_api_key_is_never_persisted(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    secrets_path = tmp_path / "secrets.json"
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config_module, "SECRETS_PATH", secrets_path)
    cfg = AppConfig(
        repo_root=str(tmp_path),
        control_plane_api_key="sk-super-secret",
        http_auth_mode="bearer",
        http_auth_token="local-http-token",
    )
    config_module.save_config(cfg)
    persisted = config_path.read_text(encoding="utf-8")
    assert "sk-super-secret" not in persisted
    assert "local-http-token" not in persisted
    assert json.loads(secrets_path.read_text(encoding="utf-8"))["http_auth_token"] == "local-http-token"


def test_nonlocal_http_requires_auth_and_allowed_hosts(tmp_path: Path) -> None:
    cfg = AppConfig(repo_root=str(tmp_path), transport="streamable-http", http_host="0.0.0.0")
    errors = cfg.validate()
    assert "http_nonlocal_auth_required" in errors
