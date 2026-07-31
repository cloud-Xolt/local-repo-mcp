from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from audit.logger import AuditLogger
from mcp.server.mcpserver import MCPServer
from repo.filesystem import RepoFilesystem
from repo.git import GitController
from sandbox.executor import SandboxExecutor
from security.policy_engine import PolicyEngine
from security.rbac import RBACEngine
from security.risk import RiskAssessment, RiskScorer
from security.scanner import SecretScanner
from session.manager import SessionManager

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_POLICY = PROJECT_ROOT / "config" / "policy.yaml"


@dataclass
class RuntimeContext:
    mcp: MCPServer
    project_root: Path
    repo_root: Path
    mcp_mode: str
    max_file_bytes: int
    max_patch_bytes: int
    allow_dirty_worktree: bool
    test_timeout_max: int
    policy: PolicyEngine
    rbac: RBACEngine
    risk: RiskScorer
    scanner: SecretScanner
    audit_logger: AuditLogger
    sessions: SessionManager
    filesystem: RepoFilesystem
    sandbox: SandboxExecutor
    git: GitController
    run_git: Callable[..., subprocess.CompletedProcess]


def build_context(mcp: MCPServer) -> RuntimeContext:
    repo_root = Path(os.environ.get("REPO_ROOT", ".")).resolve()
    policy_path = Path(os.environ.get("POLICY_RULES", str(DEFAULT_POLICY)))
    policy = PolicyEngine(policy_path, repo_root)
    rbac = RBACEngine(policy.rules)
    risk = RiskScorer(policy.rules)

    def run_git(args: list[str], input_text: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
        cmd = [
            "git",
            "-C",
            str(repo_root),
            "-c",
            f"safe.directory={repo_root}",
        ] + args
        return subprocess.run(
            cmd,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    return RuntimeContext(
        mcp=mcp,
        project_root=PROJECT_ROOT,
        repo_root=repo_root,
        mcp_mode=os.environ.get("MCP_MODE", "read").lower(),
        max_file_bytes=int(os.environ.get("MAX_FILE_BYTES", "200000")),
        max_patch_bytes=int(os.environ.get("MAX_PATCH_BYTES", "200000")),
        allow_dirty_worktree=os.environ.get("ALLOW_DIRTY_WORKTREE", "false").lower() == "true",
        test_timeout_max=int(os.environ.get("TEST_TIMEOUT_MAX", "300")),
        policy=policy,
        rbac=rbac,
        risk=risk,
        scanner=SecretScanner(),
        audit_logger=AuditLogger(os.environ.get("AUDIT_LOG", str(PROJECT_ROOT / "audit.log"))),
        sessions=SessionManager(repo_root),
        filesystem=RepoFilesystem(repo_root, policy, int(os.environ.get("MAX_FILE_BYTES", "200000"))),
        sandbox=SandboxExecutor(repo_root),
        git=GitController(repo_root, policy, run_git),
        run_git=run_git,
    )


def require_mode(ctx: RuntimeContext, *modes: str) -> None:
    if ctx.mcp_mode not in modes:
        raise PermissionError(f"tool not allowed in MCP_MODE={ctx.mcp_mode}; required={modes}")


def require_global_permission(ctx: RuntimeContext, required: str) -> None:
    order = {"read": 1, "write": 2, "test": 3, "ship": 4}
    if order.get(ctx.mcp_mode, 0) < order.get(required, 0):
        raise PermissionError(f"MCP_MODE={ctx.mcp_mode} insufficient for {required}")


def require_session(ctx: RuntimeContext, session_id: str, permission: str):
    if not session_id:
        raise PermissionError("session_id is required; call repo_session_start first")
    return ctx.sessions.require(session_id, permission)


def session_user(ctx: RuntimeContext, session_id: str) -> str:
    if not session_id:
        return ""
    session = ctx.sessions.get(session_id)
    return session.user if session else ""


def audit_tool(
    ctx: RuntimeContext,
    tool: str,
    session_id: str,
    payload: dict[str, Any],
    result: str,
    *,
    targets: list[str] | None = None,
    patch_bytes: int = 0,
    branch: str = "",
    user: str = "",
    input_hash: str = "",
    result_hash: str = "",
    assess: bool = True,
) -> RiskAssessment | None:
    assessment = None
    risk_level = "low"
    risk_score = 0
    risk_factors: list[str] = []

    if assess:
        assessment = ctx.risk.assess(
            tool,
            targets=targets,
            patch_bytes=patch_bytes,
            branch=branch or ctx.git.current_branch(),
            user=user or session_user(ctx, session_id),
        )
        risk_level = assessment.level
        risk_score = assessment.score
        risk_factors = assessment.factors

    ctx.audit_logger.log(
        tool=tool,
        session_id=session_id,
        payload=payload,
        result=result,
        risk_level=risk_level,
        target_files=targets,
        input_hash=input_hash,
        result_hash=result_hash,
        risk_score=risk_score,
        risk_factors=risk_factors,
    )
    return assessment
