from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from gui.config import AppConfig
from gui.process_manager import ProcessManager

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "launch_mcp.py"


def _resolve_python(python: Path | None = None) -> Path:
    if python is not None:
        return python.resolve()
    venv_python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if venv_python.is_file():
        return venv_python.resolve()
    return Path(sys.executable).resolve()


class TunnelManager:
    def __init__(self, processes: ProcessManager) -> None:
        self.processes = processes

    @staticmethod
    def build_mcp_command(python: Path | None = None) -> list[str]:
        py = _resolve_python(python)
        return [str(py), str(LAUNCHER.resolve())]

    @staticmethod
    def profile_path(config: AppConfig) -> Path:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "tunnel-client" / f"{config.tunnel_profile.strip() or 'local-repo'}.yaml"

    @staticmethod
    def stdio_command_text(python: Path | None = None) -> str:
        parts = TunnelManager.build_mcp_command(python)
        return " ".join(Path(part).as_posix() for part in parts)

    def repair_profile_command(self, config: AppConfig) -> bool:
        if config.transport != "stdio":
            return False
        path = self.profile_path(config)
        if not path.is_file():
            return False
        expected = self.stdio_command_text()
        content = path.read_text(encoding="utf-8")
        if expected in content and '\\"' not in content and "G:tmp" not in content:
            return False
        import re

        new_content, count = re.subn(
            r"(?m)^(\s*command:\s*).*$",
            lambda match: f'{match.group(1)}"{expected}"',
            content,
            count=1,
        )
        if count:
            path.write_text(new_content, encoding="utf-8")
            return True
        return False

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
                "--mcp-command", self.stdio_command_text(),
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

    def detect(self, config: AppConfig) -> str:
        version = self.version(config)
        path = self.profile_path(config)
        if not path.is_file():
            return version
        repair_note = ""
        if self.repair_profile_command(config):
            repair_note = "Repaired MCP command in profile.\n\n"
        if not config.control_plane_api_key.strip():
            return (
                f"{version}\n\n{repair_note}"
                f"Profile found: {path}\n"
                "Set Runtime API Key, then run Doctor for full validation."
            )
        doctor = self.doctor(config)
        return f"{version}\n\n{repair_note}{doctor}"

    def doctor(self, config: AppConfig) -> str:
        self.repair_profile_command(config)
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
