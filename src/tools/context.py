from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from audit.logger import AuditLogger
from mcp.server.mcpserver import MCPServer
from repo.filesystem import RepoFilesystem
from repo.git import GitController, run_git
from security.scanner import SecretScanner
from tools.test_runner import RepoTestRunner

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


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


def _parse_mode(raw: str) -> Literal["read", "write", "test"]:
    mode = raw.lower()
    if mode not in {"read", "write", "test"}:
        raise RuntimeError(f"unsupported MCP_MODE={raw}; allowed: read, write, test")
    return mode  # type: ignore[return-value]


def build_context(mcp: MCPServer) -> RuntimeContext:
    repo_root = Path(os.environ.get("REPO_ROOT", ".")).resolve()
    audit_path = os.environ.get("AUDIT_LOG", "").strip()
    audit = AuditLogger(audit_path) if audit_path else AuditLogger("")

    def git_runner(args: list[str], input_text: str | None = None, timeout: int = 30):
        return run_git(repo_root, args, input_text=input_text, timeout=timeout)

    max_output_bytes = int(os.environ.get("MAX_OUTPUT_BYTES", "200000"))

    return RuntimeContext(
        mcp=mcp,
        repo_root=repo_root,
        mode=_parse_mode(os.environ.get("MCP_MODE", "read")),
        max_file_bytes=int(os.environ.get("MAX_FILE_BYTES", "200000")),
        max_patch_bytes=int(os.environ.get("MAX_PATCH_BYTES", "200000")),
        max_search_results=int(os.environ.get("MAX_SEARCH_RESULTS", "50")),
        max_output_bytes=max_output_bytes,
        allow_dirty_worktree=os.environ.get("ALLOW_DIRTY_WORKTREE", "false").lower() == "true",
        filesystem=RepoFilesystem(repo_root, int(os.environ.get("MAX_FILE_BYTES", "200000"))),
        git=GitController(repo_root, git_runner, max_output_bytes),
        scanner=SecretScanner(),
        audit=audit if audit.enabled else None,
        test_runner=RepoTestRunner(repo_root),
    )


def require_mode(ctx: RuntimeContext, *modes: str) -> None:
    if ctx.mode not in modes:
        raise PermissionError(f"tool not allowed in MCP_MODE={ctx.mode}; required={modes}")


def audit_event(
    ctx: RuntimeContext,
    *,
    tool: str,
    status: str,
    target: str | None = None,
    targets: list[str] | None = None,
    input_bytes: int = 0,
    input_hash: str = "",
    result_hash: str = "",
) -> None:
    if ctx.audit is None:
        return
    ctx.audit.log(
        tool=tool,
        status=status,
        target=target,
        targets=targets,
        input_bytes=input_bytes,
        input_hash=input_hash,
        result_hash=result_hash,
    )
