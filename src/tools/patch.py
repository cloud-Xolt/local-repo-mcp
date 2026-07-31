from pathlib import Path
from typing import Any

from audit.logger import AuditLogger
from tools.context import RuntimeContext, audit_tool, require_global_permission, require_mode, require_session, session_user


def validate_patch(ctx: RuntimeContext, patch: str, session_id: str) -> dict[str, Any]:
    patch_bytes = len(patch.encode("utf-8"))
    if patch_bytes > ctx.max_patch_bytes:
        raise PermissionError(f"patch too large: {patch_bytes} bytes > {ctx.max_patch_bytes}")

    session = require_session(ctx, session_id, "write")
    ctx.rbac.require_permission(session.user, "write")
    require_global_permission(ctx, "write")
    ctx.git.require_writable_branch()

    targets = ctx.git.patch_targets(patch)

    for p in targets:
        if p.startswith("/") or ".." in Path(p).parts:
            raise PermissionError(f"unsafe patch path: {p}")
        ctx.filesystem.resolve_path(p)
        rel = str((ctx.repo_root / p).resolve().relative_to(ctx.repo_root).as_posix())
        ctx.filesystem.check_write_path(rel)

    ctx.scanner.require_clean_patch(patch)
    ctx.git.apply_patch_check(patch)

    return {
        "valid": True,
        "targets": targets,
        "patch_bytes": patch_bytes,
        "branch": ctx.git.current_branch(),
        "session_id": session_id,
        "patch_hash": AuditLogger.hash_value(patch),
    }


def ensure_clean_worktree(ctx: RuntimeContext) -> None:
    if ctx.allow_dirty_worktree:
        return
    status = ctx.git.status_short().strip()
    if status:
        raise PermissionError("worktree is not clean; refuse to apply patch")


def register_patch_tools(ctx: RuntimeContext) -> None:
    @ctx.mcp.tool()
    def repo_prepare_patch(patch: str, session_id: str) -> dict[str, Any]:
        """Validate patch via git apply --stat, policy, secret scan, git apply --check."""
        require_mode(ctx, "write", "test", "ship")
        result = validate_patch(ctx, patch, session_id=session_id)
        assessment = audit_tool(
            ctx,
            "repo_prepare_patch",
            session_id,
            {"patch_bytes": result["patch_bytes"], "targets": result["targets"]},
            "valid",
            targets=result["targets"],
            patch_bytes=result["patch_bytes"],
            branch=result["branch"],
            input_hash=result["patch_hash"],
        )
        if assessment:
            ctx.risk.require_acceptable(assessment)
        return result

    @ctx.mcp.tool()
    def repo_approve_patch(patch: str, session_id: str) -> dict[str, Any]:
        """Approve a prepared patch for apply. Must call repo_prepare_patch first."""
        require_mode(ctx, "write", "test", "ship")
        prepared = validate_patch(ctx, patch, session_id=session_id)
        patch_hash = prepared["patch_hash"]
        ctx.sessions.approve_patch(session_id, patch_hash)
        assessment = audit_tool(
            ctx,
            "repo_approve_patch",
            session_id,
            {"targets": prepared["targets"]},
            "approved",
            targets=prepared["targets"],
            patch_bytes=prepared["patch_bytes"],
            branch=prepared["branch"],
            input_hash=patch_hash,
        )
        if assessment:
            ctx.risk.require_acceptable(assessment)
        return {"approved": True, "patch_hash": patch_hash, "targets": prepared["targets"]}

    @ctx.mcp.tool()
    def repo_apply_patch(patch: str, session_id: str) -> dict[str, Any]:
        """Apply an approved patch. Does not commit or push."""
        require_mode(ctx, "write", "test", "ship")
        ensure_clean_worktree(ctx)
        prepared = validate_patch(ctx, patch, session_id=session_id)
        patch_hash = prepared["patch_hash"]
        ctx.sessions.require_approved_patch(session_id, patch_hash)

        assessment = ctx.risk.assess(
            "repo_apply_patch",
            targets=prepared["targets"],
            patch_bytes=prepared["patch_bytes"],
            branch=prepared["branch"],
            user=session_user(ctx, session_id),
        )
        ctx.risk.require_acceptable(assessment)

        ctx.git.apply_patch(patch)
        diff = ctx.git.diff()
        result_hash = AuditLogger.hash_value(diff)

        audit_tool(
            ctx,
            "repo_apply_patch",
            session_id,
            {"patch_bytes": prepared["patch_bytes"], "targets": prepared["targets"]},
            "applied",
            targets=prepared["targets"],
            patch_bytes=prepared["patch_bytes"],
            branch=prepared["branch"],
            input_hash=patch_hash,
            result_hash=result_hash,
            assess=False,
        )

        return {
            "applied": True,
            "targets": prepared["targets"],
            "branch": ctx.git.current_branch(),
            "diff": diff[: ctx.max_patch_bytes],
            "patch_hash": patch_hash,
            "risk_score": assessment.score,
        }
