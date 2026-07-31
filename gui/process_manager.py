import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from gui.config import AppConfig, PROJECT_ROOT
from gui.tunnel_manager import TunnelManager


@dataclass
class ProcessInfo:
    name: str
    proc: subprocess.Popen | None = None
    started_at: float | None = None
    log_lines: list[str] = field(default_factory=list)
    _reader_thread: threading.Thread | None = field(default=None, repr=False)

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    @property
    def uptime(self) -> str:
        if not self.running or self.started_at is None:
            return "-"
        seconds = int(time.time() - self.started_at)
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m {sec}s"
        if minutes:
            return f"{minutes}m {sec}s"
        return f"{sec}s"


class ProcessManager:
    MAX_LOG_LINES = 2000

    def __init__(self, on_log: Callable[[str, str], None] | None = None) -> None:
        self.on_log = on_log
        self.mcp = ProcessInfo(name="MCP Server")
        self.tunnel = ProcessInfo(name="Tunnel Client")
        self._lock = threading.Lock()
        self.tunnel_manager = TunnelManager(on_log=lambda line: self._append_log(self.tunnel, line))

    def _python_executable(self) -> Path:
        venv_python = PROJECT_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if venv_python.exists():
            return venv_python
        return Path(sys.executable)

    def _append_log(self, info: ProcessInfo, line: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {line}"
        with self._lock:
            info.log_lines.append(entry)
            if len(info.log_lines) > self.MAX_LOG_LINES:
                info.log_lines = info.log_lines[-self.MAX_LOG_LINES :]
        if self.on_log:
            self.on_log(info.name, entry)

    def _start_reader(self, info: ProcessInfo) -> None:
        if info.proc is None or info.proc.stdout is None:
            return

        def reader() -> None:
            assert info.proc is not None and info.proc.stdout is not None
            for raw in iter(info.proc.stdout.readline, b""):
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    self._append_log(info, line)
            code = info.proc.wait()
            self._append_log(info, f"[{info.name}] 进程已退出 (code={code})")

        info._reader_thread = threading.Thread(target=reader, daemon=True)
        info._reader_thread.start()

    def _spawn(
        self,
        info: ProcessInfo,
        cmd: list[str],
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> None:
        if info.running:
            raise RuntimeError(f"{info.name} 已在运行")

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        info.proc = subprocess.Popen(
            cmd,
            cwd=str(cwd or PROJECT_ROOT),
            env=merged_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        info.started_at = time.time()
        info.log_lines.clear()
        self._append_log(info, f"[{info.name}] 已启动: {' '.join(cmd)}")
        self._start_reader(info)

    def start_mcp(self, config: AppConfig) -> None:
        python = self._python_executable()
        server = PROJECT_ROOT / "server.py"
        self._spawn(
            self.mcp,
            [str(python), str(server)],
            env=config.mcp_env(),
            cwd=PROJECT_ROOT,
        )

    def _build_mcp_command(self, config: AppConfig) -> str:
        python = self._python_executable()
        server = PROJECT_ROOT / "server.py"
        env_parts = " ".join(f'{k}="{v}"' for k, v in config.mcp_env().items())
        if os.name == "nt":
            return (
                f'powershell -NoProfile -Command "'
                f"Set-Location '{PROJECT_ROOT}'; "
                f"{env_parts}; "
                f"& '{python}' '{server}'"
                f'"'
            )
        return (
            f"bash -lc 'cd {shlex_quote(str(PROJECT_ROOT))} && "
            f"{env_parts} {shlex_quote(str(python))} {shlex_quote(str(server))}'"
        )

    def install_tunnel(self) -> str:
        return self.tunnel_manager.install_managed()

    def tunnel_status(self, config: AppConfig):
        return self.tunnel_manager.status(config)

    def init_tunnel(self, config: AppConfig) -> None:
        self.tunnel_manager.init_profile(config, self._build_mcp_command)

    def start_tunnel(self, config: AppConfig, init_first: bool = True) -> None:
        if init_first and not self.tunnel_manager.is_profile_initialized(config.tunnel_profile):
            self.init_tunnel(config)
        cmd = self.tunnel_manager.build_run_cmd(config)
        env = self.tunnel_manager.run_env(config)
        self._spawn(self.tunnel, cmd, env=env, cwd=PROJECT_ROOT)

    def run_tunnel_doctor(self, config: AppConfig) -> str:
        return self.tunnel_manager.run_doctor(config)

    def stop(self, info: ProcessInfo) -> None:
        if not info.running or info.proc is None:
            return
        info.proc.terminate()
        try:
            info.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            info.proc.kill()
            info.proc.wait(timeout=3)
        self._append_log(info, f"[{info.name}] 已停止")
        info.proc = None
        info.started_at = None

    def stop_all(self) -> None:
        self.stop(self.tunnel)
        self.stop(self.mcp)

    def restart_tunnel(self, config: AppConfig) -> None:
        self.stop(self.tunnel)
        self.start_tunnel(config, init_first=False)

    def get_recent_logs(self, info: ProcessInfo, limit: int = 500) -> list[str]:
        with self._lock:
            return info.log_lines[-limit:]

    def tail_audit_log(self, path: str, last_size: int) -> tuple[list[str], int]:
        audit_path = Path(path)
        if not audit_path.exists():
            return [], 0
        size = audit_path.stat().st_size
        if size <= last_size:
            return [], last_size
        with audit_path.open("r", encoding="utf-8", errors="replace") as f:
            f.seek(last_size)
            new_text = f.read()
        lines = [f"[audit] {line}" for line in new_text.splitlines() if line.strip()]
        return lines, size


def shlex_quote(value: str) -> str:
    if os.name == "nt":
        return value.replace("'", "''")
    import shlex

    return shlex.quote(value)
