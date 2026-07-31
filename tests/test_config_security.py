import json
import os
from pathlib import Path

from gui.config import AppConfig, load_config, persisted_dict, save_config, CONFIG_PATH


def test_api_key_not_persisted(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("gui.config.CONFIG_PATH", tmp_path / "config.json")
    config = AppConfig(control_plane_api_key="sk-test-secret")
    save_config(config)
    data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert "control_plane_api_key" not in data
    assert "sk-test-secret" not in json.dumps(data)


def test_persisted_dict_strips_api_key() -> None:
    config = AppConfig(control_plane_api_key="sk-x")
    data = persisted_dict(config)
    assert "control_plane_api_key" not in data


def test_reload_clears_api_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("gui.config.CONFIG_PATH", tmp_path / "config.json")
    config = AppConfig(control_plane_api_key="sk-test")
    save_config(config)
    loaded = load_config()
    assert loaded.control_plane_api_key == ""


def test_config_file_mode_unix(tmp_path, monkeypatch) -> None:
    if os.name == "nt":
        return
    path = tmp_path / "config.json"
    monkeypatch.setattr("gui.config.CONFIG_PATH", path)
    save_config(AppConfig())
    assert oct(path.stat().st_mode & 0o777) == oct(0o600)
