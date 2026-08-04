from __future__ import annotations

import json
from pathlib import Path

import gui.config as config_module
from gui.config import AppConfig


def _redirect_config(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    config_path = tmp_path / "config.json"
    secrets_path = tmp_path / "secrets.json"
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config_module, "SECRETS_PATH", secrets_path)
    return config_path, secrets_path


def test_api_key_is_never_persisted(tmp_path: Path, monkeypatch) -> None:
    config_path, secrets_path = _redirect_config(tmp_path, monkeypatch)
    cfg = AppConfig(
        repo_root=str(tmp_path),
        control_plane_api_key="runtime-key-not-for-disk",
        http_auth_mode="bearer",
        http_auth_token="local-http-token",
    )
    config_module.save_config(cfg)

    persisted = config_path.read_text(encoding="utf-8")
    assert "runtime-key-not-for-disk" not in persisted
    assert "local-http-token" not in persisted
    assert secrets_path.is_file()
    assert config_module.load_config().http_auth_token == "local-http-token"


def test_http_defaults_to_bearer() -> None:
    assert AppConfig().http_auth_mode == "bearer"


def test_local_http_rejects_none(tmp_path: Path) -> None:
    cfg = AppConfig(
        repo_root=str(tmp_path),
        transport="streamable-http",
        http_auth_mode="none",
        http_auth_token="unused",
    )
    assert "http_auth_required" in cfg.validate()


def test_nonlocal_http_requires_hosts(tmp_path: Path) -> None:
    cfg = AppConfig(
        repo_root=str(tmp_path),
        transport="streamable-http",
        http_host="0.0.0.0",
        http_auth_mode="bearer",
        http_auth_token="token",
        http_allowed_hosts="",
    )
    assert "http_nonlocal_hosts_required" in cfg.validate()


def test_load_migrates_legacy_http_config(tmp_path: Path, monkeypatch) -> None:
    config_path, _ = _redirect_config(tmp_path, monkeypatch)
    config_path.write_text(
        json.dumps(
            {
                "repo_root": str(tmp_path),
                "transport": "streamable-http",
                "http_auth_mode": "none",
                "audit_log": "",
            }
        ),
        encoding="utf-8",
    )
    loaded = config_module.load_config()
    assert loaded.http_auth_mode == "bearer"
    assert len(loaded.http_auth_token) >= 32
    assert loaded.audit_log
