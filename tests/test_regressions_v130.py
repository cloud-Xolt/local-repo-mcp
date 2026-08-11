from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import repo.search as search_module
from gui.config import AppConfig
from gui.runtime_config import apply_to_environment
from gui.config_codec import coerce_dataclass
from gui.config_io import read_json_object
from gui.processes import ManagedProcess, ProcessManager
from mcp_app.version import VERSION
from repo.controller import GitController
from repo.git import run_git
from repo.lock import RepositoryLock
from repo.search import search_repository
from security.guard import validate_read_path


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "tests@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Tests"],
        check=True,
    )


def test_explicit_environment_has_priority(tmp_path: Path, monkeypatch) -> None:
    explicit = str(tmp_path / "explicit")
    monkeypatch.setenv("REPO_ROOT", explicit)
    config = AppConfig(repo_root=str(tmp_path / "persisted"))
    apply_to_environment(config, override=False)
    assert os.environ["REPO_ROOT"] == explicit


def test_malformed_config_is_quarantined(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{broken", encoding="utf-8")
    assert read_json_object(path) == {}
    assert not path.exists()
    assert list(tmp_path.glob("config.invalid.*.json"))


def test_config_type_coercion_uses_safe_defaults() -> None:
    assert coerce_dataclass(
        AppConfig, {"allow_dirty_worktree": "true"}
    ).allow_dirty_worktree is True
    assert coerce_dataclass(
        AppConfig, {"allow_dirty_worktree": "invalid"}
    ).allow_dirty_worktree is False


def test_remote_http_requires_tls_but_supports_native_tls(tmp_path: Path) -> None:
    _git_init(tmp_path)
    base = dict(
        repo_root=str(tmp_path),
        transport="streamable-http",
        http_host="0.0.0.0",
        http_auth_token="token",
        http_allowed_hosts="example.test",
    )
    assert "http_nonlocal_tls_required" in AppConfig(**base).validate()

    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("certificate", encoding="utf-8")
    key.write_text("private-key", encoding="utf-8")
    secure = AppConfig(
        **base,
        http_tls_certfile=str(cert),
        http_tls_keyfile=str(key),
    )
    assert "http_nonlocal_tls_required" not in secure.validate()


def test_python_search_fallback_is_bounded_and_filters_sensitive_files(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "app.py").write_text("needle\nneedle\n", encoding="utf-8")
    (tmp_path / ".env").write_text("needle\n", encoding="utf-8")
    monkeypatch.setattr(search_module.shutil, "which", lambda name: None)
    result = search_repository("needle", tmp_path, 1, 10_000, 10_000)
    assert result["backend"] == "python"
    assert result["truncated"] is True
    assert [item["path"] for item in result["matches"]] == ["app.py"]


def test_hardlinked_file_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("secret", encoding="utf-8")
    linked = tmp_path / "linked.txt"
    try:
        os.link(outside, linked)
    except OSError:
        pytest.skip("hard links are unavailable")
    with pytest.raises(PermissionError):
        validate_read_path(tmp_path, "linked.txt")


def test_repository_lock_blocks_second_writer(tmp_path: Path) -> None:
    with RepositoryLock(tmp_path, timeout=1):
        with pytest.raises(TimeoutError):
            with RepositoryLock(tmp_path, timeout=0.1):
                pass


def test_git_status_uses_rename_destination(tmp_path: Path) -> None:
    _git_init(tmp_path)
    source = tmp_path / "old.txt"
    source.write_text("content", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "old.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "initial"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "mv", "old.txt", "new.txt"],
        check=True,
    )

    controller = GitController(
        tmp_path,
        lambda args, input_text=None, timeout=30: run_git(
            tmp_path, args, input_text=input_text, timeout=timeout
        ),
        20_000,
    )
    entries = controller.status_filtered()["entries"]
    assert entries == [{"status": "R ", "path": "new.txt"}]


def test_process_stability_detects_early_exit() -> None:
    process = ManagedProcess("short-lived")
    process.start([sys.executable, "-c", "pass"])
    with pytest.raises(RuntimeError):
        ProcessManager.ensure_process_stable(process, delay=0.5)


def test_shared_version() -> None:
    assert VERSION == "1.4.0"


def test_pyproject_uses_shared_version_and_entrypoints() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert payload["project"]["dynamic"] == ["version"]
    assert payload["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "mcp_app.version.VERSION"
    }
    assert payload["project"]["scripts"]["local-repo-mcp"] == "mcp_app.launcher:main"
