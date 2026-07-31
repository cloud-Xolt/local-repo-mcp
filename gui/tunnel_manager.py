"""tunnel-client 外部安装：仅路径检测、profile、doctor、启停。"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from gui.config import AppConfig, PROJECT_ROOT

TUNNEL_DATA_DIR = PROJECT_ROOT / "data" / "tunnel"
TUNNEL_PROFILE_DIR = TUNNEL_DATA_DIR / "profiles"
TUNNEL_STATE_FILE = TUNNEL_DATA_DIR / "state.json"


@dataclass
class TunnelState:
    profile_initialized: bool = False
    last_doctor_ok: bool = False
    last_doctor_at: int = 0
    last_error: str = ""


@dataclass
class TunnelStatus:
    executable: str
    version: str
    installed: bool
    profile_dir: str
    profile_initialized: bool
    profiles: list[str]
    state: TunnelState


class TunnelManager:
    def __init__(self, on_log: Callable[[str], None] | None = None) -> None:
        self.on_log = on_log
        TUNNEL_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    def _log(self, msg: str) -> None:
        if self.on_log:
            self.on_log(msg)

    def resolve_executable(self, config: AppConfig) -> Path:
        if not config.tunnel_client_path.strip():
            raise FileNotFoundError("请指定 tunnel-client 可执行文件路径")
        path = Path(config.tunnel_client_path.strip())
        if not path.exists():
            raise FileNotFoundError(f"tunnel-client 路径不存在: {path}")
        return path

    def api_key(self, config: AppConfig) -> str:
        return config.control_plane_api_key.strip() or os.environ.get("CONTROL_PLANE_API_KEY", "").strip()

    def tunnel_env(self, config: AppConfig) -> dict[str, str]:
        env = {"TUNNEL_CLIENT_PROFILE_DIR": str(TUNNEL_PROFILE_DIR)}
        key = self.api_key(config)
        if key:
            env["CONTROL_PLANE_API_KEY"] = key
        if config.tunnel_id.strip():
            env["CONTROL_PLANE_TUNNEL_ID"] = config.tunnel_id.strip()
        return env

    def load_state(self) -> TunnelState:
        if not TUNNEL_STATE_FILE.exists():
            return TunnelState()
        data = json.loads(TUNNEL_STATE_FILE.read_text(encoding="utf-8"))
        return TunnelState(**{k: data.get(k, v) for k, v in asdict(TunnelState()).items()})

    def save_state(self, state: TunnelState) -> None:
        TUNNEL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        TUNNEL_STATE_FILE.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")

    def get_version(self, config: AppConfig) -> str:
        exe = self.resolve_executable(config)
        result = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode != 0:
            return result.stderr.strip() or "unknown"
        return (result.stdout or result.stderr).strip()

    def list_profiles(self) -> list[str]:
        if not TUNNEL_PROFILE_DIR.exists():
            return []
        return sorted(p.stem for p in TUNNEL_PROFILE_DIR.glob("*.yaml"))

    def is_profile_initialized(self, profile: str) -> bool:
        return (TUNNEL_PROFILE_DIR / f"{profile}.yaml").exists()

    def status(self, config: AppConfig) -> TunnelStatus:
        state = self.load_state()
        try:
            exe = self.resolve_executable(config)
            version = self.get_version(config)
            installed = True
        except FileNotFoundError:
            exe = Path(config.tunnel_client_path or "")
            version = ""
            installed = False
        profile = config.tunnel_profile.strip() or "local-repo"
        return TunnelStatus(
            executable=str(exe),
            version=version,
            installed=installed,
            profile_dir=str(TUNNEL_PROFILE_DIR),
            profile_initialized=self.is_profile_initialized(profile),
            profiles=self.list_profiles(),
            state=state,
        )

    def build_mcp_command(self, python_executable: Path) -> list[str]:
        launcher = PROJECT_ROOT / "launch_mcp.py"
        return [str(python_executable), str(launcher.resolve())]

    def init_profile(self, config: AppConfig, python_executable: Path) -> None:
        exe = self.resolve_executable(config)
        mcp_cmd = self.build_mcp_command(python_executable)
        cmd = [
            str(exe),
            "init",
            "--sample",
            "sample_mcp_stdio_local",
            "--profile",
            config.tunnel_profile,
            "--tunnel-id",
            config.tunnel_id.strip(),
            "--mcp-command",
            " ".join(mcp_cmd),
        ]
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, **self.tunnel_env(config)},
            capture_output=True,
            text=True,
            timeout=120,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            state = self.load_state()
            state.last_error = output.strip()[:500]
            self.save_state(state)
            raise RuntimeError(output.strip() or f"tunnel-client init 失败 (code={result.returncode})")

        import time

        state = self.load_state()
        state.profile_initialized = True
        state.last_error = ""
        self.save_state(state)
        for line in output.splitlines():
            if line.strip():
                self._log(f"[Tunnel] {line.strip()}")

    def run_doctor(self, config: AppConfig) -> str:
        exe = self.resolve_executable(config)
        result = subprocess.run(
            [str(exe), "doctor", "--profile", config.tunnel_profile, "--explain"],
            cwd=str(PROJECT_ROOT),
            env={**os.environ, **self.tunnel_env(config)},
            capture_output=True,
            text=True,
            timeout=120,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        output = (result.stdout or "") + (result.stderr or "")
        import time

        state = self.load_state()
        state.last_doctor_at = int(time.time())
        state.last_doctor_ok = result.returncode == 0
        if result.returncode != 0:
            state.last_error = output.strip()[:500]
            self.save_state(state)
            raise RuntimeError(output.strip() or f"tunnel-client doctor 失败 (code={result.returncode})")
        state.last_error = ""
        self.save_state(state)
        return output.strip()

    def build_run_cmd(self, config: AppConfig) -> list[str]:
        exe = self.resolve_executable(config)
        return [str(exe), "run", "--profile", config.tunnel_profile]

    def run_env(self, config: AppConfig) -> dict[str, str]:
        return self.tunnel_env(config)
