from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable

from gui.config import AppConfig

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "launch_mcp.py"


class ManagedProcess:
    def __init__(self, name: str, max_log_lines: int = 2000) -> None:
        self.name = name
        self.process: subprocess.Popen[str] | None = None
        self.started_at: float | None = None
        self.logs: deque[str] = deque(maxlen=max_log_lines)
        self._reader: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.running and self.process else None

    @property
    def uptime(self) -> int:
        if not self.running or self.started_at is None:
            return 0
        return max(0, int(time.time() - self.started_at))

    def append_log(self, line: str) -> None:
        with self._lock:
            self.logs.append(line.rstrip("\r\n"))

    def start(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> None:
        if self.running:
            raise RuntimeError(f"{self.name} is already running")
        self.logs.clear()
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            command,
            cwd=str(cwd or ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        self.started_at = time.time()
        self.append_log(f"$ {' '.join(command)}")
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()

    def _read_output(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        for line in iter(process.stdout.readline, ""):
            if not line:
                break
            self.append_log(line)
        code = process.poll()
        self.append_log(f"[{self.name} exited with code {code}]")

    def stop(self, timeout: float = 5.0) -> None:
        process = self.process
        if process is None or process.poll() is not None:
            self.process = None
            self.started_at = None
            return
        process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        self.append_log(f"[{self.name} stopped]")
        self.process = None
        self.started_at = None

    def snapshot(self) -> list[str]:
        with self._lock:
            return list(self.logs)


class ProcessManager:
    def __init__(self) -> None:
        self.mcp = ManagedProcess("MCP")
        self.tunnel = ManagedProcess("Tunnel")

    def start_http(self, config: AppConfig) -> None:
        if config.transport != "streamable-http":
            raise RuntimeError("Persistent MCP process is available only for Streamable HTTP")
        env = os.environ.copy()
        env.update(config.mcp_env())
        env["MCP_TRANSPORT"] = "streamable-http"
        self.mcp.start([sys.executable, str(LAUNCHER)], env=env, cwd=ROOT)

    def restart_http(self, config: AppConfig) -> None:
        self.mcp.stop()
        self.start_http(config)

    def stop_all(self) -> None:
        self.tunnel.stop()
        self.mcp.stop()


def format_uptime(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
