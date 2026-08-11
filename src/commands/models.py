from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Literal

CommandKind = Literal["test", "build", "lint", "check"]
CommandStatus = Literal["success", "failed", "timeout", "output_limit"]


@dataclass(frozen=True)
class CommandSpec:
    """Immutable description of one allowlisted repository command."""

    key: str
    kind: CommandKind
    argv: tuple[str, ...]

    def display_command(self) -> str:
        return " ".join(shlex.quote(part) for part in self.argv)


@dataclass(frozen=True)
class CommandResult:
    """Normalized, verifiable result for a command that was started."""

    spec: CommandSpec
    status: CommandStatus
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    timeout_seconds: int
    duration_ms: int

    @property
    def success(self) -> bool:
        return self.status == "success"

    def as_dict(self) -> dict:
        return {
            "command_key": self.spec.key,
            "command_kind": self.spec.kind,
            "argv": list(self.spec.argv),
            "command": self.spec.display_command(),
            "status": self.status,
            "success": self.success,
            "exit_code": self.exit_code,
            # Compatibility with clients written against <= 1.3.x.
            "returncode": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "timeout_seconds": self.timeout_seconds,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class CommandBatchResult:
    """Sequential batch result; no scheduler or background task semantics."""

    requested: tuple[str, ...]
    results: tuple[CommandResult, ...]
    stop_on_failure: bool

    @property
    def success(self) -> bool:
        return len(self.results) == len(self.requested) and all(
            item.success for item in self.results
        )

    @property
    def status(self) -> str:
        return "success" if self.success else "failed"

    def as_dict(self) -> dict:
        return {
            "batch": True,
            "status": self.status,
            "success": self.success,
            "requested_count": len(self.requested),
            "completed_count": len(self.results),
            "stop_on_failure": self.stop_on_failure,
            "requested": list(self.requested),
            "remaining": list(self.requested[len(self.results):]),
            "duration_ms": sum(item.duration_ms for item in self.results),
            "results": [item.as_dict() for item in self.results],
        }
