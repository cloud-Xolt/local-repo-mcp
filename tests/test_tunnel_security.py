import pytest

from gui.config import AppConfig
from gui.process_manager import ProcessManager
from gui import tunnel_manager as tm


def test_tunnel_manager_has_no_install() -> None:
    assert not hasattr(tm.TunnelManager, "install_managed")


def test_mcp_start_uses_launcher(monkeypatch) -> None:
    captured: dict = {}

    def fake_spawn(self, info, cmd, env=None, cwd=None):
        captured["cmd"] = cmd

    monkeypatch.setattr(ProcessManager, "_spawn", fake_spawn)
    pm = ProcessManager()
    pm.start_mcp(AppConfig(repo_root="."))
    assert any("launch_mcp.py" in part for part in captured["cmd"])


def test_tunnel_init_mcp_command_uses_launcher() -> None:
    manager = tm.TunnelManager()
    cmd = manager.build_mcp_command(__import__("pathlib").Path("python"))
    assert any("launch_mcp.py" in part for part in cmd)
    assert "bash" not in " ".join(cmd)
    assert "powershell" not in " ".join(cmd)
