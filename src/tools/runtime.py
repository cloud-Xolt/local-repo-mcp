from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from audit.logger import AuditLogger
from mcp.server.mcpserver import MCPServer
from repo.controller import GitController
from repo.filesystem import RepoFilesystem
from repo.git import run_git
from repo.lock import RepositoryLock
from repo.worktree import require_worktree_root
from security.scanner import SecretScanner
from tools.test_runner import RepoTestRunner


@dataclass
class RuntimeContext:
    mcp: MCPServer
    repo_root: Path
    mode: Literal["read", "write", "test"]
    transport: str
    server_instance_id: str
    max_file_bytes: int
    max_patch_bytes: int
    max_search_results: int
    max_output_bytes: int
    allow_dirty_worktree: bool
    filesystem: RepoFilesystem
    git: GitController
    scanner: SecretScanner
    audit: AuditLogger | None
    runtime_log: AuditLogger | None
    test_runner: RepoTestRunner
    patch_lock: RepositoryLock


def _positive_int(name: str, default: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero")
    return min(value, maximum)


def _parse_mode(value: str) -> Literal["read", "write", "test"]:
    mode = value.strip().lower()
    if mode not in {"read", "write", "test"}:
        raise RuntimeError(
            f"unsupported MCP_MODE={value}; allowed: read, write, test"
        )
    return mode  # type: ignore[return-value]


def build_context(mcp: MCPServer) -> RuntimeContext:
    repo_text = os.environ.get("REPO_ROOT", "").strip()
    if not repo_text:
        raise RuntimeError("REPO_ROOT is required")
    repo_root = require_worktree_root(repo_text).root
    assert repo_root is not None

    max_file = _positive_int("MAX_FILE_BYTES", 200_000, 20_000_000)
    max_patch = _positive_int("MAX_PATCH_BYTES", 200_000, 5_000_000)
    max_search = _positive_int("MAX_SEARCH_RESULTS", 50, 1000)
    max_output = _positive_int("MAX_OUTPUT_BYTES", 20_000, 2_000_000)
    test_timeout = _positive_int("TEST_TIMEOUT_MAX", 300, 1800)
    log_max = _positive_int("LOG_MAX_BYTES", 5_000_000, 100_000_000)
    log_backups = _positive_int("LOG_BACKUP_COUNT", 3, 20)
    audit = AuditLogger(
        os.environ.get("AUDIT_LOG", "").strip(),
        max_bytes=log_max,
        backup_count=log_backups,
    )
    runtime_log = AuditLogger(
        os.environ.get("MCP_LOG", "").strip(),
        max_bytes=log_max,
        backup_count=log_backups,
    )

    def runner(args: list[str], input_text: str | None = None, timeout: int = 30):
        return run_git(repo_root, args, input_text=input_text, timeout=timeout)

    context = RuntimeContext(
        mcp=mcp,
        repo_root=repo_root,
        mode=_parse_mode(os.environ.get("MCP_MODE", "read")),
        transport=os.environ.get("MCP_TRANSPORT", "stdio").strip().lower(),
        server_instance_id=secrets.token_hex(8),
        max_file_bytes=max_file,
        max_patch_bytes=max_patch,
        max_search_results=max_search,
        max_output_bytes=max_output,
        allow_dirty_worktree=os.environ.get(
            "ALLOW_DIRTY_WORKTREE", "false"
        ).lower()
        == "true",
        filesystem=RepoFilesystem(repo_root, max_file),
        git=GitController(repo_root, runner, max_output),
        scanner=SecretScanner(),
        audit=audit if audit.enabled else None,
        runtime_log=(
            runtime_log
            if runtime_log.enabled and runtime_log.path != audit.path
            else None
        ),
        test_runner=RepoTestRunner(repo_root, max_output, test_timeout),
        patch_lock=RepositoryLock(repo_root),
    )
    audit_event(context, event="server_start", status="success")
    return context


def require_mode(context: RuntimeContext, *modes: str) -> None:
    if context.mode not in modes:
        raise PermissionError(
            f"tool not allowed in MCP_MODE={context.mode}; required={modes}"
        )


def audit_event(context: RuntimeContext, **record) -> None:
    audit = context.audit
    runtime_log = context.runtime_log
    if audit is None and runtime_log is None:
        return
    payload = {
        "event_id": secrets.token_hex(12),
        "server_instance_id": context.server_instance_id,
        "transport": context.transport,
        "mode": context.mode,
        "repository": context.repo_root.name,
        "repository_hash": AuditLogger.hash_value(str(context.repo_root)),
        "process_id": os.getpid(),
    }
    payload.update(record)
    if audit is not None:
        audit.log(**payload)
    if runtime_log is not None:
        runtime_log.log(**payload)


def repository_info(context: RuntimeContext) -> dict[str, str]:
    return {"name": context.repo_root.name, "root": str(context.repo_root)}
