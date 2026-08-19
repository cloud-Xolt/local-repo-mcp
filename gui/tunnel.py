from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from gui.config import AppConfig
from gui.processes import ProcessManager
from mcp_app.runtime import launcher_command

ROOT = Path(__file__).resolve().parents[1]


def _resolve_python(python: Path | None = None) -> Path:
    if python is not None:
        return python.expanduser().resolve()
    venv_python = ROOT / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    return venv_python.resolve() if venv_python.is_file() else Path(sys.executable).resolve()


def _profile_base_dir() -> Path:
    try:
        home = Path.home()
    except RuntimeError:
        home = ROOT.parent
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "").strip()
        return Path(os.path.expandvars(appdata)) / "tunnel-client" if appdata else (
            home / "AppData" / "Roaming" / "tunnel-client"
        )
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "tunnel-client"
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    return Path(os.path.expandvars(xdg)).expanduser() / "tunnel-client" if xdg else (
        home / ".config" / "tunnel-client"
    )


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        delete=False,
    ) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def command_text(parts: list[str]) -> str:
    normalized = [
        Path(part).as_posix() if ("/" in part or "\\" in part) else part
        for part in parts
    ]
    return subprocess.list2cmdline(normalized) if os.name == "nt" else shlex.join(normalized)


def _command_slots(value: Any) -> list[tuple[dict[str, Any], str]]:
    matches: list[tuple[dict[str, Any], str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "command" and isinstance(item, str):
                if "launch_mcp.py" in item or "mcp_app.launcher" in item:
                    matches.append((value, key))
            else:
                matches.extend(_command_slots(item))
    elif isinstance(value, list):
        for item in value:
            matches.extend(_command_slots(item))
    return matches


class TunnelManager:
    def __init__(self, processes: ProcessManager) -> None:
        self.processes = processes

    def _record(self, action: str, output: str = "") -> None:
        self.processes.tunnel.append_log(action)
        for line in output.splitlines():
            self.processes.tunnel.append_log(line)

    @staticmethod
    def build_mcp_command(python: Path | None = None) -> list[str]:
        return launcher_command(_resolve_python(python))

    @staticmethod
    def stdio_command_text(python: Path | None = None) -> str:
        return command_text(TunnelManager.build_mcp_command(python))

    @staticmethod
    def profile_path(config: AppConfig) -> Path:
        explicit = config.tunnel_profile_path.strip()
        if explicit:
            return Path(explicit).expanduser().resolve()
        profile = config.tunnel_profile.strip() or "local-repo"
        return _profile_base_dir() / f"{profile}.yaml"

    def repair_profile_command(self, config: AppConfig) -> bool:
        if config.transport != "stdio":
            return False
        path = self.profile_path(config)
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        try:
            payload = yaml.safe_load(original)
        except yaml.YAMLError as exc:
            raise RuntimeError(f"invalid tunnel profile YAML: {path}") from exc
        if not isinstance(payload, (dict, list)):
            raise RuntimeError("tunnel profile must contain a YAML mapping or list")
        matches = _command_slots(payload)
        if not matches:
            return False
        if len(matches) != 1:
            raise RuntimeError(
                "tunnel profile contains multiple Local Repo MCP commands; "
                "select an unambiguous profile"
            )
        container, key = matches[0]
        expected = self.stdio_command_text()
        if str(container[key]).strip() == expected:
            return False
        container[key] = expected
        rendered = yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            _write_atomic(backup, original)
        _write_atomic(path, rendered)
        return True

    @staticmethod
    def resolve_executable(config: AppConfig) -> str:
        raw = config.tunnel_client_path.strip() or "tunnel-client"
        expanded = str(Path(raw).expanduser()) if raw != "tunnel-client" else raw
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
            [executable, "--version"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=10,
            check=False,
            shell=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "failed to read tunnel-client version")
        return result.stdout.strip() or result.stderr.strip() or executable

    @staticmethod
    def _runtime_env(config: AppConfig) -> dict[str, str]:
        api_key = config.control_plane_api_key.strip()
        if not api_key:
            raise ValueError("CONTROL_PLANE_API_KEY is required")
        environment = os.environ.copy()
        environment["CONTROL_PLANE_API_KEY"] = api_key
        return environment

    def init_profile(self, config: AppConfig) -> str:
        if config.transport != "stdio":
            raise RuntimeError(
                "Automatic HTTP Tunnel setup is disabled because Streamable HTTP "
                "requires an explicit Bearer token"
            )
        if not config.tunnel_id.strip():
            raise ValueError("Tunnel ID is required")
        if not config.tunnel_profile.strip():
            raise ValueError("Tunnel profile is required")
        command = [
            self.resolve_executable(config),
            "init",
            "--profile",
            config.tunnel_profile.strip(),
            "--tunnel-id",
            config.tunnel_id.strip(),
            "--sample",
            "sample_mcp_stdio_local",
            "--mcp-command",
            self.stdio_command_text(),
        ]
        result = subprocess.run(
            command,
            env=self._runtime_env(config),
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=60,
            check=False,
            shell=False,
        )
        output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        if result.returncode != 0:
            self._record("Tunnel profile initialization failed", output)
            raise RuntimeError(output or "tunnel-client init failed")
        final = output or "Profile initialized"
        self._record("Tunnel profile initialized", final)
        return final

    def doctor(self, config: AppConfig) -> str:
        self.repair_profile_command(config)
        result = subprocess.run(
            [
                self.resolve_executable(config),
                "doctor",
                "--profile",
                config.tunnel_profile.strip(),
                "--explain",
            ],
            env=self._runtime_env(config),
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=60,
            check=False,
            shell=False,
        )
        output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        if result.returncode != 0:
            self._record("Tunnel Doctor failed", output)
            raise RuntimeError(output or "tunnel-client doctor failed")
        final = output or "Doctor passed"
        self._record("Tunnel Doctor completed", final)
        return final

    def detect(self, config: AppConfig) -> str:
        version = self.version(config)
        profile = self.profile_path(config)
        if not profile.is_file():
            return version
        repaired = self.repair_profile_command(config)
        note = "Repaired MCP command in profile.\n\n" if repaired else ""
        if not config.control_plane_api_key.strip():
            return f"{version}\n\n{note}Profile found: {profile}\nSet Runtime API Key, then run Doctor."
        return f"{version}\n\n{note}{self.doctor(config)}"

    def prepare(self, config: AppConfig) -> str:
        messages = [self.version(config)]
        if not self.profile_path(config).is_file():
            messages.append(self.init_profile(config))
        messages.append(self.doctor(config))
        return "\n\n".join(messages)

    def start(self, config: AppConfig) -> None:
        if config.transport == "streamable-http" and not self.processes.mcp.running:
            raise RuntimeError("Start the Streamable HTTP MCP server before the Tunnel")
        prepared = self.prepare(config)
        self._record("Tunnel prepared", prepared)
        self.processes.tunnel.start(
            [
                self.resolve_executable(config),
                "run",
                "--profile",
                config.tunnel_profile.strip(),
            ],
            env=self._runtime_env(config),
            cwd=ROOT,
            clear_logs=False,
        )
        self.processes.ensure_process_stable(self.processes.tunnel)
