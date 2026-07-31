"""tunnel-client 本地纳管：安装、Profile、生命周期。"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from gui.config import AppConfig, PROJECT_ROOT

TUNNEL_BIN_DIR = PROJECT_ROOT / "bin" / "tunnel-client"
TUNNEL_DATA_DIR = PROJECT_ROOT / "data" / "tunnel"
TUNNEL_PROFILE_DIR = TUNNEL_DATA_DIR / "profiles"
TUNNEL_STATE_FILE = TUNNEL_DATA_DIR / "state.json"
GITHUB_LATEST_API = "https://api.github.com/repos/openai/tunnel-client/releases/latest"


@dataclass
class TunnelState:
    installed_version: str = ""
    installed_at: int = 0
    profile_initialized: bool = False
    last_doctor_ok: bool = False
    last_doctor_at: int = 0
    last_error: str = ""


@dataclass
class TunnelStatus:
    managed: bool
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
        TUNNEL_BIN_DIR.mkdir(parents=True, exist_ok=True)
        TUNNEL_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    def _log(self, msg: str) -> None:
        if self.on_log:
            self.on_log(msg)

    def managed_executable(self) -> Path:
        name = "tunnel-client.exe" if os.name == "nt" else "tunnel-client"
        return TUNNEL_BIN_DIR / name

    def resolve_executable(self, config: AppConfig) -> Path:
        managed = self.managed_executable()
        if managed.exists():
            return managed
        if config.tunnel_client_path.strip():
            path = Path(config.tunnel_client_path.strip())
            if path.exists():
                return path
            raise FileNotFoundError(f"tunnel-client 路径不存在: {path}")
        found = shutil.which("tunnel-client")
        if found:
            return Path(found)
        raise FileNotFoundError(
            "tunnel-client 未安装。纯本地 MCP 不需要；ChatGPT 接入请到 Tunnel 页安装。"
        )

    def tunnel_env(self, config: AppConfig) -> dict[str, str]:
        env = {
            "TUNNEL_CLIENT_PROFILE_DIR": str(TUNNEL_PROFILE_DIR),
            "CONTROL_PLANE_API_KEY": config.control_plane_api_key.strip(),
        }
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

    def _platform_asset_suffix(self) -> str:
        system = sys.platform
        machine = platform.machine().lower()
        arm = machine in ("arm64", "aarch64")
        if system == "win32":
            return "windows-arm64" if arm else "windows-amd64"
        if system == "darwin":
            return "darwin-arm64" if arm else "darwin-amd64"
        return "linux-arm64" if arm else "linux-amd64"

    def _fetch_latest_asset_url(self) -> tuple[str, str]:
        req = urllib.request.Request(
            GITHUB_LATEST_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "local-repo-mcp-gui"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            release = json.loads(resp.read().decode("utf-8"))
        tag = release.get("tag_name", "")
        suffix = self._platform_asset_suffix()
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(f"{suffix}.zip"):
                return tag, asset["browser_download_url"]
        raise RuntimeError(f"未找到当前平台发布包: {suffix}.zip (release {tag})")

    def install_managed(self) -> str:
        tag, url = self._fetch_latest_asset_url()
        self._log(f"[Tunnel] 下载 {tag} ({self._platform_asset_suffix()})...")
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "tunnel-client.zip"
            urllib.request.urlretrieve(url, zip_path)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(TUNNEL_BIN_DIR)
        exe = self.managed_executable()
        if not exe.exists():
            for candidate in TUNNEL_BIN_DIR.rglob("tunnel-client*"):
                if candidate.is_file() and candidate.suffix not in (".zip", ".txt"):
                    shutil.copy2(candidate, exe)
                    break
        if not exe.exists():
            raise RuntimeError("安装完成但未找到 tunnel-client 可执行文件")
        if os.name != "nt":
            exe.chmod(exe.stat().st_mode | 0o111)

        import time

        state = self.load_state()
        state.installed_version = tag
        state.installed_at = int(time.time())
        state.last_error = ""
        self.save_state(state)
        self._log(f"[Tunnel] 已纳管到 {exe} ({tag})")
        return tag

    def get_version(self, config: AppConfig) -> str:
        exe = self.resolve_executable(config)
        result = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
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
        managed_path = self.managed_executable()
        try:
            exe = self.resolve_executable(config)
            version = self.get_version(config)
            installed = True
        except FileNotFoundError:
            exe = managed_path
            version = ""
            installed = False
        profile = config.tunnel_profile.strip() or "local-repo"
        profiles = self.list_profiles()
        initialized = self.is_profile_initialized(profile)
        return TunnelStatus(
            managed=managed_path.exists(),
            executable=str(exe),
            version=version,
            installed=installed,
            profile_dir=str(TUNNEL_PROFILE_DIR),
            profile_initialized=initialized,
            profiles=profiles,
            state=state,
        )

    def init_profile(self, config: AppConfig, build_mcp_command: Callable[[AppConfig], str]) -> None:
        exe = self.resolve_executable(config)
        mcp_command = build_mcp_command(config)
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
            mcp_command,
        ]
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, **self.tunnel_env(config)},
            capture_output=True,
            text=True,
            timeout=120,
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
