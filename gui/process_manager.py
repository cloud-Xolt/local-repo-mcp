from __future__ import annotations

import atexit
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

from gui.config import AppConfig

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "launch_mcp.py"


class _WindowsKillOnCloseJob:
    """Kill the full child process tree when the GUI process exits."""

    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

    def __init__(self) -> None:
        self.handle = None
        if os.name != "nt":
            return

        import ctypes
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
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

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
        ]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            return
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        configured = kernel32.SetInformationJobObject(
            handle,
            self.JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not configured:
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
        self._windows_job: _WindowsKillOnCloseJob | None = None

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
            self._windows_job = _WindowsKillOnCloseJob()
            if not self._windows_job.assign(self.process):
                self.append_log(f"[{self.name} warning: Windows Job Object unavailable]")
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

    def _force_process_tree(self, process: subprocess.Popen[str]) -> None:
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

        if os.name == "nt" and self._windows_job is not None:
            self._windows_job.close()
            self._windows_job = None
        elif os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                process.terminate()
        else:
            process.terminate()

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if force:
                self._force_process_tree(process)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass

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
        atexit.register(self.force_stop_all)

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
