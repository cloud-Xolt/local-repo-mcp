import secrets
import sys

import pytest
import yaml
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
    profile.write_text(
        "health:\n  listen_addr: 127.0.0.1:9090\n",
        encoding="utf-8",
    )
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
        if command[1] == "admin":
            return Result()
        if command[1] == "health":
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
    monkeypatch.setattr(tm.TunnelManager, "wait_control_plane_ready", lambda self, config: "ok")

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

    assert [part[1] for part in calls] == [
        "--version",
        "doctor",
        "admin",
    ]
    assert started == [["tunnel-client", "run", "--profile", "local-repo"]]


def test_sync_profile_tunnel_id_updates_mismatch(tmp_path, monkeypatch) -> None:
    profile_dir = tmp_path / "tunnel-client"
    profile_dir.mkdir()
    profile = profile_dir / "local-repo.yaml"
    profile.write_text(
        "control_plane:\n  tunnel_id: tunnel_old\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tm, "_profile_base_dir", lambda: profile_dir)
    config = AppConfig(
        repo_root=".",
        tunnel_profile="local-repo",
        tunnel_id="tunnel_new",
        transport="stdio",
    )
    manager = tm.TunnelManager(tm.ProcessManager())
    message = manager.sync_profile_tunnel_id(config)
    assert message is not None
    assert "tunnel_old" in message
    assert "tunnel_new" in message
    saved = yaml.safe_load(profile.read_text(encoding="utf-8"))
    assert saved["control_plane"]["tunnel_id"] == "tunnel_new"


def test_sync_profile_tunnel_id_noop_when_matching(tmp_path, monkeypatch) -> None:
    profile_dir = tmp_path / "tunnel-client"
    profile_dir.mkdir()
    profile = profile_dir / "local-repo.yaml"
    profile.write_text(
        "control_plane:\n  tunnel_id: tunnel_same\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tm, "_profile_base_dir", lambda: profile_dir)
    config = AppConfig(
        repo_root=".",
        tunnel_profile="local-repo",
        tunnel_id="tunnel_same",
        transport="stdio",
    )
    manager = tm.TunnelManager(tm.ProcessManager())
    assert manager.sync_profile_tunnel_id(config) is None


def test_verify_control_plane_credentials_rejects_invalid_key(
    tmp_path, monkeypatch
) -> None:
    profile_dir = tmp_path / "tunnel-client"
    profile_dir.mkdir()

    def fake_run(command, **kwargs):
        class Result:
            returncode = 1
            stdout = ""
            stderr = "401 Unauthorized: invalid API key"
        return Result()

    monkeypatch.setattr(tm.subprocess, "run", fake_run)
    monkeypatch.setattr(tm, "_profile_base_dir", lambda: profile_dir)
    monkeypatch.setattr(
        tm.TunnelManager,
        "resolve_executable",
        lambda self, config: "tunnel-client",
    )
    config = AppConfig(
        repo_root=".",
        tunnel_profile="local-repo",
        tunnel_id="tunnel_test",
        control_plane_api_key="bad-key",
        transport="stdio",
    )
    manager = tm.TunnelManager(tm.ProcessManager())
    with pytest.raises(tm.ControlPlaneCLIError, match="rejected by the OpenAI control plane"):
        manager.verify_control_plane_credentials(config)


def test_verify_control_plane_credentials_reports_network_error(
    tmp_path, monkeypatch
) -> None:
    profile_dir = tmp_path / "tunnel-client"
    profile_dir.mkdir()
    attempts = {"count": 0}

    def fake_run(command, **kwargs):
        attempts["count"] += 1
        class Result:
            returncode = 1
            stdout = ""
            stderr = (
                'Get "https://api.openai.com/v1/tunnels/tunnel_test": '
                "dial tcp 108.160.167.165:443: connectex: connection attempt failed"
            )
        return Result()

    monkeypatch.setattr(tm.subprocess, "run", fake_run)
    monkeypatch.setattr(tm.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(tm, "_profile_base_dir", lambda: profile_dir)
    monkeypatch.setattr(
        tm.TunnelManager,
        "resolve_executable",
        lambda self, config: "tunnel-client",
    )
    config = AppConfig(
        repo_root=".",
        tunnel_profile="local-repo",
        tunnel_id="tunnel_test",
        control_plane_api_key="secret",
        transport="stdio",
    )
    manager = tm.TunnelManager(tm.ProcessManager())
    with pytest.raises(tm.ControlPlaneCLIError, match="network or proxy issue"):
        manager.verify_control_plane_credentials(config)
    assert attempts["count"] == 3


def test_control_plane_prefers_network_over_generic_403() -> None:
    message = tm.TunnelManager._control_plane_error_message(
        'Get "https://api.openai.com/v1/tunnels/x": dial tcp: i/o timeout\n403 Forbidden'
    )
    assert "network or proxy issue" in message


def test_runtime_env_omits_proxy_when_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    config = AppConfig(
        repo_root=".",
        control_plane_api_key="secret",
    )
    env = tm.TunnelManager._runtime_env(config)
    assert "HTTPS_PROXY" not in env
    assert "HTTP_PROXY" not in env


def test_runtime_env_uses_configured_tunnel_proxy(monkeypatch) -> None:
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    config = AppConfig(
        repo_root=".",
        control_plane_api_key="secret",
        tunnel_http_proxy="http://127.0.0.1:7897",
    )
    env = tm.TunnelManager._runtime_env(config)
    assert env["HTTPS_PROXY"] == "http://127.0.0.1:7897"
    assert env["HTTP_PROXY"] == "http://127.0.0.1:7897"


def test_runtime_env_respects_existing_https_proxy(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8888")
    config = AppConfig(
        repo_root=".",
        control_plane_api_key="secret",
        tunnel_http_proxy="http://127.0.0.1:7897",
    )
    env = tm.TunnelManager._runtime_env(config)
    assert env["HTTPS_PROXY"] == "http://127.0.0.1:8888"
    assert "HTTP_PROXY" not in env or env.get("HTTP_PROXY") != "http://127.0.0.1:7897"


def test_health_base_url_reads_profile_listen_addr(tmp_path, monkeypatch) -> None:
    profile_dir = tmp_path / "tunnel-client"
    profile_dir.mkdir()
    profile = profile_dir / "local-repo.yaml"
    profile.write_text(
        "health:\n  listen_addr: 127.0.0.1:9090\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tm, "_profile_base_dir", lambda: profile_dir)
    config = AppConfig(repo_root=".", tunnel_profile="local-repo", transport="stdio")
    assert tm.TunnelManager.health_base_url(config) == "http://127.0.0.1:9090"


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
