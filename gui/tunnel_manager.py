from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from gui.config import AppConfig
from gui.process_manager import ProcessManager

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "launch_mcp.py"


class TunnelManager:
    def __init__(self, processes: ProcessManager) -> None:
        self.processes = processes

    @staticmethod
    def resolve_executable(config: AppConfig) -> str:
        raw = config.tunnel_client_path.strip() or "tunnel-client"
        expanded = str(Path(raw).expanduser()) if raw not in {"tunnel-client"} else raw
        resolved = shutil.which(expanded)
        if resolved:
            return resolved
        candidate = Path(expanded)
        if candidate.is_file():
            return str(candidate.resolve())
        raise FileNotFoundError("tunnel-client executable was not found")

    def version(self, config: AppConfig) -> str:
        executable = self.resolve_executable(config)
        result = subprocess.run(
            [executable, "--version"], text=True, capture_output=True,
            timeout=10, check=False, shell=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "failed to read tunnel-client version")
        return result.stdout.strip() or result.stderr.strip() or executable

    @staticmethod
    def _runtime_env(config: AppConfig) -> dict[str, str]:
        if not config.control_plane_api_key.strip():
            raise ValueError("CONTROL_PLANE_API_KEY is required")
        env = os.environ.copy()
        env["CONTROL_PLANE_API_KEY"] = config.control_plane_api_key.strip()
        return env

    @staticmethod
    def _stdio_command_text() -> str:
        command = [sys.executable, str(LAUNCHER)]
        return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)

    def init_profile(self, config: AppConfig) -> str:
        executable = self.resolve_executable(config)
        if not config.tunnel_id.strip():
            raise ValueError("Tunnel ID is required")
        if not config.tunnel_profile.strip():
            raise ValueError("Tunnel profile is required")
        command = [
            executable, "init", "--profile", config.tunnel_profile.strip(),
            "--tunnel-id", config.tunnel_id.strip(),
        ]
        if config.transport == "stdio":
            command.extend([
                "--sample", "sample_mcp_stdio_local",
                "--mcp-command", self._stdio_command_text(),
            ])
        else:
            if config.http_auth_mode == "bearer":
                raise RuntimeError(
                    "HTTP Tunnel setup with a custom Bearer token is not automated. "
                    "Use STDIO Tunnel or configure tunnel-client manually."
                )
            command.extend(["--mcp-server-url", config.endpoint_url()])
        result = subprocess.run(
            command, env=self._runtime_env(config), cwd=ROOT,
            text=True, capture_output=True, timeout=60, check=False, shell=False,
        )
        output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        if result.returncode != 0:
            raise RuntimeError(output or "tunnel-client init failed")
        return output or "Profile initialized"

    def doctor(self, config: AppConfig) -> str:
        executable = self.resolve_executable(config)
        result = subprocess.run(
            [executable, "doctor", "--profile", config.tunnel_profile.strip(), "--explain"],
            env=self._runtime_env(config), cwd=ROOT,
            text=True, capture_output=True, timeout=60, check=False, shell=False,
        )
        output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        if result.returncode != 0:
            raise RuntimeError(output or "tunnel-client doctor failed")
        return output or "Doctor passed"

    def start(self, config: AppConfig) -> None:
        executable = self.resolve_executable(config)
        if config.transport == "streamable-http" and not self.processes.mcp.running:
            raise RuntimeError("Start the Streamable HTTP MCP server before starting the Tunnel")
        self.processes.tunnel.start(
            [executable, "run", "--profile", config.tunnel_profile.strip()],
            env=self._runtime_env(config), cwd=ROOT,
        )
