import secrets
import sys

import pytest
from pathlib import Path

from gui.config import AppConfig
from gui.processes import ManagedProcess, ProcessManager
from gui import tunnel as tm


def test_tunnel_manager_has_no_install() -> None:
    assert not hasattr(tm.TunnelManager, "install_managed")


def test_http_start_uses_launcher(monkeypatch) -> None:
    captured: dict = {}

    def fake_start(self, command, *, env=None, cwd=None):
        captured["cmd"] = command

    monkeypatch.setattr(ManagedProcess, "start", fake_start)
    monkeypatch.setattr(ProcessManager, "_wait_http_ready", lambda self, config: None)
    pm = ProcessManager()
    pm.start_http(AppConfig(repo_root=".", transport="streamable-http", http_auth_token=secrets.token_urlsafe(32)))
    assert any("launch_mcp.py" in part for part in captured["cmd"])


def test_tunnel_init_mcp_command_uses_launcher() -> None:
    cmd = tm.TunnelManager.build_mcp_command(Path("python"))
    assert any("launch_mcp.py" in part for part in cmd)
    text = tm.TunnelManager.stdio_command_text(Path("python"))
    assert "launch_mcp.py" in text
    assert '"' not in text
    assert "\\" not in text
    assert "bash" not in text
    assert "powershell" not in text


def test_start_prepares_profile_before_run(tmp_path, monkeypatch) -> None:
    profile_dir = tmp_path / "tunnel-client"
    profile_dir.mkdir()
    profile = profile_dir / "local-repo.yaml"
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""
        if command[1] == "--version":
            return Result()
        if command[1] == "init":
            profile.write_text("mcp: {}\n", encoding="utf-8")
            return Result()
        if command[1] == "doctor":
            return Result()
        if command[1] == "run":
            return Result()
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(tm.subprocess, "run", fake_run)
    monkeypatch.setattr(tm, "_profile_base_dir", lambda: profile_dir)
    monkeypatch.setattr(
        tm.TunnelManager,
        "resolve_executable",
        lambda self, config: "tunnel-client",
    )
    monkeypatch.setattr(
        tm.ProcessManager,
        "ensure_process_stable",
        lambda self, process: None,
    )

    started: list[list[str]] = []

    def fake_start(self, command, *, env=None, cwd=None, clear_logs=True):
        started.append(command)

    monkeypatch.setattr(ManagedProcess, "start", fake_start)

    config = AppConfig(
        repo_root=".",
        tunnel_profile="local-repo",
        tunnel_id="tunnel_test",
        control_plane_api_key="secret",
        transport="stdio",
    )
    manager = tm.TunnelManager(tm.ProcessManager())
    manager.start(config)

    assert [part[1] for part in calls] == ["--version", "init", "doctor"]
    assert started == [["tunnel-client", "run", "--profile", "local-repo"]]


def test_repair_profile_command_rewrites_broken_yaml(tmp_path, monkeypatch) -> None:
    profile_dir = tmp_path / "tunnel-client"
    profile_dir.mkdir()
    profile = profile_dir / "local-repo.yaml"
    profile.write_text(
        'mcp:\n  commands:\n    - channel: main\n'
        '      command: "G:\\\\tmp\\\\local-repo-mcp\\\\.venv\\\\Scripts\\\\python.exe '
        'G:\\\\tmp\\\\local-repo-mcp\\\\launch_mcp.py"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(tm, "_profile_base_dir", lambda: profile_dir)
    config = AppConfig(repo_root=".", tunnel_profile="local-repo", transport="stdio")
    manager = tm.TunnelManager(tm.ProcessManager())
    assert manager.repair_profile_command(config) is True
    saved = profile.read_text(encoding="utf-8")
    assert "G:/" in saved or "python" in saved
    assert "\\\\" not in saved
    assert "launch_mcp.py" in saved
