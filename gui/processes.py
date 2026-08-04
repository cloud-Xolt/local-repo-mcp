from __future__ import annotations

import atexit
import json
import os
import signal
import ssl
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from audit.logger import AuditLogger
from gui.config import AppConfig
from gui.log_safety import redact_log_text
from gui.runtime_config import environment_for
from mcp_app.runtime import launcher_command

ROOT = Path(__file__).resolve().parents[1]


class _WindowsJob:
    """Terminate the complete child tree when the GUI exits."""

    def __init__(self) -> None:
        self.handle = None
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]

        class BASIC_LIMITS(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class EXTENDED_LIMITS(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMITS),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
        ]
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            return
        limits = EXTENDED_LIMITS()
        limits.BasicLimitInformation.LimitFlags = 0x00002000
        if not kernel32.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            kernel32.CloseHandle(handle)
            return
        self._kernel32 = kernel32
        self._wintypes = wintypes
        self.handle = handle

    def assign(self, process: subprocess.Popen[str]) -> bool:
        if self.handle is None or os.name != "nt":
            return False
        process_handle = self._wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
        return bool(self._kernel32.AssignProcessToJobObject(self.handle, process_handle))

    def close(self) -> None:
        if self.handle is not None:
            self._kernel32.CloseHandle(self.handle)
            self.handle = None


class ManagedProcess:
    def __init__(self, name: str, max_log_lines: int = 2000) -> None:
        self.name = name
        self.process: subprocess.Popen[str] | None = None
        self.started_at: float | None = None
        self.logs: deque[str] = deque(maxlen=max_log_lines)
        self._reader: threading.Thread | None = None
        self._lock = threading.Lock()
        self._windows_job: _WindowsJob | None = None

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
        text = redact_log_text(line.rstrip("\r\n"))
        if not text:
            return
        with self._lock:
            self.logs.append(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {text}")

    def start(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        clear_logs: bool = True,
    ) -> None:
        if self.running:
            raise RuntimeError(f"{self.name} is already running")
        if clear_logs:
            self.logs.clear()
        creationflags = 0
        if os.name == "nt":
            creationflags = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
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
            start_new_session=os.name != "nt",
        )
        if os.name == "nt":
            self._windows_job = _WindowsJob()
            if not self._windows_job.assign(self.process):
                self.append_log(f"[{self.name} warning: Windows Job Object unavailable]")
        self.started_at = time.time()
        self.append_log("$ " + subprocess.list2cmdline(command))
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
        code = process.wait()
        if code == 0:
            self.append_log(f"[{self.name} exited successfully]")
        else:
            self.append_log(f"[{self.name} error: exited with code {code}]")

    def _kill_tree(self, process: subprocess.Popen[str]) -> None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                shell=False,
            )
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()

    def stop(self, timeout: float = 3.0, *, force: bool = True) -> None:
        process = self.process
        if process is None or process.poll() is not None:
            if self._windows_job is not None:
                self._windows_job.close()
            self._windows_job = None
            self.process = None
            self.started_at = None
            return
        if os.name == "nt":
            self._kill_tree(process) if force else process.terminate()
            if self._windows_job is not None:
                self._windows_job.close()
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if force:
                self._kill_tree(process)
        self.append_log(f"[{self.name} stopped]")
        self._windows_job = None
        self.process = None
        self.started_at = None

    def snapshot(self) -> list[str]:
        with self._lock:
            return list(self.logs)

    def failure_summary(self, lines: int = 25) -> str:
        snapshot = self.snapshot()
        return "\n".join(snapshot[-max(lines, 1):]) if snapshot else (
            f"{self.name} exited without log output"
        )


def _health_url(config: AppConfig) -> str:
    if config.http_tls_terminated_proxy:
        endpoint = urlsplit(config.endpoint_url())
        return urlunsplit((endpoint.scheme, endpoint.netloc, "/healthz", "", ""))
    return config.runtime_health_url()


def _tls_context(config: AppConfig, url: str) -> ssl.SSLContext:
    parsed = urlsplit(url)
    cafile = None
    if parsed.scheme == "https" and not config.http_tls_terminated_proxy:
        cafile = config.http_tls_certfile.strip() or None
    context = ssl.create_default_context(cafile=cafile)
    if config.http_client_certfile.strip() and config.http_client_keyfile.strip():
        context.load_cert_chain(config.http_client_certfile, config.http_client_keyfile)
    return context


class ProcessManager:
    def __init__(self) -> None:
        self.mcp = ManagedProcess("MCP")
        self.tunnel = ManagedProcess("Tunnel")
        atexit.register(self.force_stop_all)

    @staticmethod
    def ensure_process_stable(process: ManagedProcess, delay: float = 1.0) -> None:
        deadline = time.monotonic() + delay
        while time.monotonic() < deadline:
            if not process.running:
                raise RuntimeError(process.failure_summary())
            time.sleep(0.05)

    def _wait_http_ready(self, config: AppConfig, timeout: float = 15.0) -> None:
        deadline = time.monotonic() + timeout
        last_error = "service did not become ready"
        health_url = _health_url(config)
        parsed = urlsplit(health_url)
        handlers = [ProxyHandler({})]
        if parsed.scheme == "https":
            handlers.append(HTTPSHandler(context=_tls_context(config, health_url)))
        opener = build_opener(*handlers)

        while time.monotonic() < deadline:
            if not self.mcp.running:
                raise RuntimeError(self.mcp.failure_summary())
            try:
                request = Request(
                    health_url,
                    headers={"Authorization": f"Bearer {config.http_auth_token}"},
                    method="GET",
                )
                with opener.open(request, timeout=1.5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                expected = AuditLogger.hash_value(
                    str(Path(config.repo_root).expanduser().resolve())
                )
                if payload.get("status") != "ok":
                    last_error = "health endpoint returned a non-ready status"
                elif payload.get("repository_hash") != expected:
                    last_error = "MCP repository identity does not match configuration"
                else:
                    return
            except (OSError, URLError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
            time.sleep(0.15)

        summary = self.mcp.failure_summary()
        self.mcp.stop(timeout=1.0, force=True)
        raise RuntimeError(f"HTTP MCP failed readiness check: {last_error}\n{summary}")

    def start_http(self, config: AppConfig) -> None:
        if config.transport != "streamable-http":
            raise RuntimeError(
                "Persistent MCP process is available only for Streamable HTTP"
            )
        environment = os.environ.copy()
        environment.update(environment_for(config))
        environment["MCP_TRANSPORT"] = "streamable-http"
        self.mcp.start(
            launcher_command(sys.executable),
            env=environment,
            cwd=ROOT,
        )
        self._wait_http_ready(config)

    def stop_all(self) -> None:
        self.force_stop_all()

    def force_stop_all(self) -> None:
        self.tunnel.stop(timeout=1.5, force=True)
        self.mcp.stop(timeout=1.5, force=True)


def format_uptime(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
