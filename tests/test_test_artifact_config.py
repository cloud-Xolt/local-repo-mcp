from __future__ import annotations

import inspect
from pathlib import Path

import gui.config as config_module
from gui.config import AppConfig
from gui.desktop import LocalRepoMCPApp
from gui.i18n import tr


def test_default_test_artifact_settings_are_internally_valid() -> None:
    errors = [key for key in AppConfig().validate() if key.startswith("test_")]
    assert errors == []


def test_test_artifact_settings_persist_and_export(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    secrets_path = tmp_path / "secrets.json"
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config_module, "SECRETS_PATH", secrets_path)

    config_module.save_config(
        AppConfig(
            repo_root=str(tmp_path),
            test_artifact_dir="qa-artifacts/screens",
            max_test_images=4,
            max_test_image_bytes=1_500_000,
            max_test_image_total_bytes=3_000_000,
        )
    )
    loaded = config_module.load_config()

    assert loaded.test_artifact_dir == "qa-artifacts/screens"
    assert loaded.max_test_images == 4
    assert loaded.max_test_image_bytes == 1_500_000
    assert loaded.max_test_image_total_bytes == 3_000_000
    environment = loaded.mcp_env()
    assert environment["TEST_ARTIFACT_DIR"] == "qa-artifacts/screens"
    assert environment["MAX_TEST_IMAGES"] == "4"
    assert environment["MAX_TEST_IMAGE_BYTES"] == "1500000"
    assert environment["MAX_TEST_IMAGE_TOTAL_BYTES"] == "3000000"


def test_test_artifact_settings_reject_unsafe_or_excessive_values() -> None:
    config = AppConfig(
        test_artifact_dir="../outside",
        max_test_images=21,
        max_test_image_bytes=9 * 1024 * 1024,
        max_test_image_total_bytes=9 * 1024 * 1024,
    )
    errors = set(config.validate())

    assert "test_artifact_dir_invalid" in errors
    assert "test_max_images_invalid" in errors
    assert "test_image_max_invalid" in errors
    assert "test_image_total_invalid" in errors


def test_desktop_advanced_settings_bind_all_test_artifact_controls() -> None:
    init_source = inspect.getsource(LocalRepoMCPApp._init_variables)
    home_source = inspect.getsource(LocalRepoMCPApp._build_home)
    collect_source = inspect.getsource(LocalRepoMCPApp._collect_config)
    for token in (
        "test_artifact_dir_var",
        "test_max_images_var",
        "test_image_max_kb_var",
        "test_image_total_kb_var",
    ):
        assert token in init_source
        assert token in home_source or token in collect_source
    for key in (
        "test_max_images",
        "test_image_max_kb",
        "test_image_total_kb",
        "test_artifact_dir",
    ):
        assert f'self.t("{key}")' in home_source
        assert tr("zh", key) != key
        assert tr("en", key) != key


def test_user_tunable_test_limits_are_not_environment_only() -> None:
    environment = AppConfig().mcp_env()
    expected_environment = {
        "MAX_FILE_BYTES",
        "MAX_PATCH_BYTES",
        "MAX_SEARCH_RESULTS",
        "MAX_OUTPUT_BYTES",
        "TEST_TIMEOUT_MAX",
        "LOG_MAX_BYTES",
        "LOG_BACKUP_COUNT",
        "TEST_ARTIFACT_DIR",
        "MAX_TEST_IMAGES",
        "MAX_TEST_IMAGE_BYTES",
        "MAX_TEST_IMAGE_TOTAL_BYTES",
    }
    assert expected_environment.issubset(environment)

    source = "\n".join(
        (
            inspect.getsource(LocalRepoMCPApp._init_variables),
            inspect.getsource(LocalRepoMCPApp._build_home),
            inspect.getsource(LocalRepoMCPApp._collect_config),
        )
    )
    for token in ("max_file_var", "max_patch_var", "max_search_var", "max_output_var", "test_timeout_var", "log_max_kb_var", "log_backup_var", "test_artifact_dir_var", "test_max_images_var", "test_image_max_kb_var", "test_image_total_kb_var"):
        assert token in source
