from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from audit.logger import AuditLogger
from mcp.server.mcpserver import MCPServer
from repo.filesystem import RepoFilesystem
from repo.git import GitController, run_git
from security.scanner import SecretScanner
from tools.test_runner import RepoTestRunner


@dataclass
class RuntimeContext:
    mcp: MCPServer
    repo_root: Path
    mode: Literal["read", "write", "test"]
    max_file_bytes: int
    max_patch_bytes: int
    max_search_results: int
    max_output_bytes: int
    allow_dirty_worktree: bool
    filesystem: RepoFilesystem
    git: GitController
    scanner: SecretScanner
    audit: AuditLogger | None
    test_runner: RepoTestRunner


def _positive_int(name: str, default: int, maximum: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero")
    return min(value, maximum)


def _parse_mode(value: str) -> Literal["read", "write", "test"]:
    mode = value.strip().lower()
    if mode not in {"read", "write", "test"}:
        raise RuntimeError(f"unsupported MCP_MODE={value}; allowed: read, write, test")
    return mode  # type: ignore[return-value]


def build_context(mcp: MCPServer) -> RuntimeContext:
    repo_root = Path(os.environ.get("REPO_ROOT", ".")).expanduser().resolve()
    max_file = _positive_int("MAX_FILE_BYTES", 200_000, 20_000_000)
    max_patch = _positive_int("MAX_PATCH_BYTES", 200_000, 5_000_000)
    max_search = _positive_int("MAX_SEARCH_RESULTS", 50, 1000)
    max_output = _positive_int("MAX_OUTPUT_BYTES", 20_000, 2_000_000)
    test_timeout = _positive_int("TEST_TIMEOUT_MAX", 300, 1800)
    audit_path = os.environ.get("AUDIT_LOG", "").strip()
    audit = AuditLogger(audit_path)

    def runner(args: list[str], input_text: str | None = None, timeout: int = 30):
        return run_git(repo_root, args, input_text=input_text, timeout=timeout)

    return RuntimeContext(
        mcp=mcp,
        repo_root=repo_root,
        mode=_parse_mode(os.environ.get("MCP_MODE", "read")),
        max_file_bytes=max_file,
        max_patch_bytes=max_patch,
        max_search_results=max_search,
        max_output_bytes=max_output,
        allow_dirty_worktree=os.environ.get("ALLOW_DIRTY_WORKTREE", "false").lower() == "true",
        filesystem=RepoFilesystem(repo_root, max_file),
        git=GitController(repo_root, runner, max_output),
        scanner=SecretScanner(),
        audit=audit if audit.enabled else None,
        test_runner=RepoTestRunner(repo_root, max_output, test_timeout),
    )


def require_mode(ctx: RuntimeContext, *modes: str) -> None:
    if ctx.mode not in modes:
        raise PermissionError(f"tool not allowed in MCP_MODE={ctx.mode}; required={modes}")


def audit_event(ctx: RuntimeContext, **record) -> None:
    if ctx.audit is not None:
        ctx.audit.log(**record)
