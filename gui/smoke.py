from __future__ import annotations

from gui import log_workspace, server_workspace
from gui.app import ASSETS
from gui.config import AppConfig
from gui.desktop import LocalRepoMCPApp
from gui.processes import ManagedProcess, ProcessManager
from gui.readiness import native_tls_probe_target
from gui.tool_visuals import TOOL_VISUALS
from gui.tunnel import TunnelManager, command_text


def main() -> None:
    required_methods = (
        "_build_home",
        "_build_server",
        "_build_chatgpt",
        "_build_logs_center",
        "_build_about",
        "_run_smoke_test",
    )
    missing = [name for name in required_methods if not callable(getattr(LocalRepoMCPApp, name, None))]
    if missing:
        raise RuntimeError(f"GUI composition root is incomplete: {missing}")
    if not callable(log_workspace.build) or not callable(server_workspace.build):
        raise RuntimeError("GUI workspaces are not callable")
    if len(TOOL_VISUALS) != 8 or len({item.name for item in TOOL_VISUALS}) != 8:
        raise RuntimeError("tool visual catalog is incomplete")
    for name in ("app-icon-16.png", "app-icon-32.png", "app-icon-64.png", "app-icon.ico"):
        if not (ASSETS / name).is_file():
            raise RuntimeError(f"missing GUI asset: {name}")
    process = ManagedProcess("smoke")
    process.append_log("smoke")
    manager = ProcessManager()
    TunnelManager(manager)
    target = native_tls_probe_target(
        AppConfig(
            transport="streamable-http",
            http_host="0.0.0.0",
            http_port=8443,
            http_public_url="https://mcp.example.test/mcp",
        )
    )
    if target[:3] != ("127.0.0.1", 8443, "mcp.example.test"):
        raise RuntimeError("native TLS readiness target is invalid")
    if not command_text(["python", "-m", "mcp_app.launcher"]):
        raise RuntimeError("tunnel command rendering failed")
    manager.force_stop_all()
    print("GUI smoke checks passed")


if __name__ == "__main__":
    main()
