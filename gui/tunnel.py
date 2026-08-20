from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

from gui.config import AppConfig
from gui.processes import ProcessManager
from mcp_app.runtime import launcher_command

ROOT = Path(__file__).resolve().parents[1]


class ControlPlaneCLIError(RuntimeError):
    def __init__(self, output: str) -> None:
        self.output = output
        super().__init__(TunnelManager._control_plane_error_message(output))


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

    @staticmethod
    def profile_tunnel_id(config: AppConfig) -> str:
        path = TunnelManager.profile_path(config)
        if not path.is_file():
            return ""
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            return ""
        if not isinstance(payload, dict):
            return ""
        control_plane = payload.get("control_plane")
        if not isinstance(control_plane, dict):
            return ""
        return str(control_plane.get("tunnel_id", "")).strip()

    def sync_profile_tunnel_id(self, config: AppConfig) -> str | None:
        expected = config.tunnel_id.strip()
        if not expected:
            raise ValueError("Tunnel ID is required")
        path = self.profile_path(config)
        if not path.is_file():
            return None
        original = path.read_text(encoding="utf-8")
        try:
            payload = yaml.safe_load(original)
        except yaml.YAMLError as exc:
            raise RuntimeError(f"invalid tunnel profile YAML: {path}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("tunnel profile must contain a YAML mapping")
        control_plane = payload.get("control_plane")
        if not isinstance(control_plane, dict):
            control_plane = {}
            payload["control_plane"] = control_plane
        current = str(control_plane.get("tunnel_id", "")).strip()
        if current == expected:
            return None
        control_plane["tunnel_id"] = expected
        rendered = yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
        _write_atomic(path, rendered)
        message = f"Profile tunnel_id updated: {current or '(empty)'} -> {expected}"
        self._record("Synced Tunnel ID in profile", message)
        return message

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
        proxy = config.tunnel_http_proxy.strip()
        if proxy and not environment.get("HTTPS_PROXY") and not environment.get("https_proxy"):
            environment["HTTPS_PROXY"] = proxy
            environment["HTTP_PROXY"] = proxy
        return environment

    @staticmethod
    def _is_network_error(output: str) -> bool:
        lowered = output.lower()
        return any(
            token in lowered
            for token in (
                "dial tcp",
                "connectex",
                "connection attempt failed",
                "connection refused",
                "connection reset",
                "connection timed out",
                "i/o timeout",
                "no such host",
                "network is unreachable",
                "failed to respond",
                "tls handshake timeout",
                "proxyconnect",
                "temporary failure in name resolution",
            )
        )

    @staticmethod
    def _is_auth_error(output: str) -> bool:
        lowered = output.lower()
        return any(
            token in lowered
            for token in (
                "401",
                "403",
                "unauthorized",
                "invalid api key",
                "authentication",
                "permission denied",
            )
        )

    @classmethod
    def _control_plane_error_message(cls, output: str) -> str:
        if cls._is_auth_error(output):
            return (
                "Runtime API Key was rejected by the OpenAI control plane. "
                "Check the key and Tunnel ID."
            )
        if cls._is_network_error(output):
            return (
                "Cannot reach the OpenAI control plane (api.openai.com). "
                "This is a network or proxy issue, not proof that the API Key is wrong. "
                "Check VPN/proxy, firewall rules, or Tunnel HTTP proxy in GUI advanced settings."
            )
        cleaned = output.strip()
        return cleaned or "control plane verification failed"

    def _run_cli(
        self,
        config: AppConfig,
        args: list[str],
        *,
        timeout: float,
        action: str,
    ) -> str:
        result = subprocess.run(
            [self.resolve_executable(config), *args],
            env=self._runtime_env(config),
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
        output = "\n".join(
            part for part in (result.stdout.strip(), result.stderr.strip()) if part
        )
        if result.returncode != 0:
            self._record(f"{action} failed", output)
            raise ControlPlaneCLIError(output)
        return output or action

    @staticmethod
    def health_base_url(config: AppConfig) -> str:
        path = TunnelManager.profile_path(config)
        if path.is_file():
            try:
                payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError:
                payload = None
            if isinstance(payload, dict):
                health = payload.get("health")
                if isinstance(health, dict):
                    listen = str(health.get("listen_addr", "")).strip()
                    if listen:
                        if listen.startswith(("http://", "https://")):
                            return listen.rstrip("/")
                        return f"http://{listen}"
        return "http://127.0.0.1:8080"

    def verify_control_plane_credentials(self, config: AppConfig) -> str:
        tunnel_id = config.tunnel_id.strip()
        if not tunnel_id:
            raise ValueError("Tunnel ID is required")
        last_error = ""
        for attempt in range(3):
            try:
                output = self._run_cli(
                    config,
                    ["admin", "tunnels", "get", tunnel_id],
                    timeout=30,
                    action="Control plane credential verification",
                )
                self._record("Control plane credentials verified", output)
                return output
            except ControlPlaneCLIError as exc:
                last_error = str(exc)
                if attempt >= 2 or not self._is_network_error(exc.output):
                    raise
                self._record(
                    "Control plane credential verification retry",
                    f"attempt {attempt + 2}/3 after network error",
                )
                time.sleep(2)
        raise RuntimeError(last_error or "control plane verification failed")

    def _tunnel_log_tail(self, *, lines: int = 30) -> str:
        tail = list(self.processes.tunnel.logs)[-lines:]
        return "\n".join(tail) if tail else "(no tunnel log output)"

    def wait_control_plane_ready(
        self,
        config: AppConfig,
        *,
        timeout: float = 180,
        poll_interval: float = 3,
        warmup: float = 5,
    ) -> str:
        base_url = self.health_base_url(config)
        if warmup > 0:
            time.sleep(warmup)
        deadline = time.monotonic() + timeout
        last_output = ""
        while time.monotonic() < deadline:
            result = subprocess.run(
                [
                    self.resolve_executable(config),
                    "health",
                    "--url",
                    base_url,
                    "--require-control-plane-poll",
                ],
                env=self._runtime_env(config),
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=15,
                check=False,
                shell=False,
            )
            last_output = "\n".join(
                part for part in (result.stdout.strip(), result.stderr.strip()) if part
            )
            if result.returncode == 0:
                self._record("Control plane poll verified", last_output)
                return last_output
            time.sleep(poll_interval)
        self.processes.tunnel.stop()
        self._record("Control plane poll verification failed", last_output)
        profile_id = self.profile_tunnel_id(config)
        gui_id = config.tunnel_id.strip()
        mismatch = ""
        if profile_id and gui_id and profile_id != gui_id:
            mismatch = (
                f"Tunnel ID mismatch: GUI={gui_id}, profile={profile_id}\n\n"
            )
        raise RuntimeError(
            "Tunnel started locally but did not connect to the OpenAI control plane "
            "within the wait window.\n\n"
            f"{mismatch}{last_output}\n\n"
            "If API Key verification passed just before start, check the Tunnel log "
            "for control-plane auth or MCP startup errors.\n\n"
            f"Recent tunnel log:\n{self._tunnel_log_tail()}"
        )

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
        else:
            synced = self.sync_profile_tunnel_id(config)
            if synced:
                messages.append(synced)
        messages.append(self.doctor(config))
        messages.append(self.verify_control_plane_credentials(config))
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
        self.wait_control_plane_ready(config)
