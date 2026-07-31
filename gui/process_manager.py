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

    def _python_executable(self) -> Path:
        venv_python = PROJECT_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if venv_python.exists():
            return venv_python
        return Path(sys.executable)

    def _tunnel_executable(self, config: AppConfig) -> str:
        if config.tunnel_client_path.strip():
            return config.tunnel_client_path.strip()
        found = shutil.which("tunnel-client")
        if found:
            return found
        raise FileNotFoundError("未找到 tunnel-client，请安装或在设置中指定路径")

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

    def init_tunnel(self, config: AppConfig) -> None:
        tunnel_exe = self._tunnel_executable(config)
        mcp_command = self._build_mcp_command(config)
        cmd = [
            tunnel_exe,
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
        env = {"CONTROL_PLANE_API_KEY": config.control_plane_api_key.strip()}
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, **env},
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            raise RuntimeError(output.strip() or f"tunnel-client init 失败 (code={result.returncode})")
        self._append_log(self.tunnel, "[Tunnel Client] tunnel profile 初始化成功")
        for line in output.splitlines():
            if line.strip():
                self._append_log(self.tunnel, line.strip())

    def start_tunnel(self, config: AppConfig) -> None:
        tunnel_exe = self._tunnel_executable(config)
        self.init_tunnel(config)
        self._spawn(
            self.tunnel,
            [tunnel_exe, "run", "--profile", config.tunnel_profile],
            env={"CONTROL_PLANE_API_KEY": config.control_plane_api_key.strip()},
            cwd=PROJECT_ROOT,
        )

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
