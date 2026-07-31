from __future__ import annotations

from typing import Any

from audit.logger import AuditLogger
from repo.git import reject_unsupported_patch_types
from tools.context import RuntimeContext, audit_event, require_mode


def ensure_clean_worktree(ctx: RuntimeContext) -> None:
    if ctx.allow_dirty_worktree:
        return
    if not ctx.git.is_worktree_clean():
        raise PermissionError("worktree is not clean; refuse to apply patch")


def register_patch_tools(ctx: RuntimeContext) -> None:
    @ctx.mcp.tool()
    def repo_apply_patch(patch: str) -> dict[str, Any]:
        """
        Apply one validated unified text patch to the configured repository.

        The tool never checks out branches, commits, resets, rebases, merges,
        pulls, or pushes. It only applies validated text changes.
        """
        require_mode(ctx, "write", "test")

        patch_bytes = len(patch.encode("utf-8"))
        if patch_bytes > ctx.max_patch_bytes:
            raise PermissionError(f"patch exceeds limit: {patch_bytes} > {ctx.max_patch_bytes}")

        reject_unsupported_patch_types(patch)
        targets = ctx.git.patch_targets(patch)

        for target in targets:
            ctx.filesystem.check_write_path(target)

        ctx.scanner.require_clean_patch(patch)
        ensure_clean_worktree(ctx)
        ctx.git.apply_patch_check(patch)
        ctx.git.apply_patch(patch)

        diff_result = ctx.git.diff_filtered(staged=False)
        patch_hash = AuditLogger.hash_value(patch)
        result_hash = AuditLogger.hash_value(diff_result.get("diff", ""))

        audit_event(
            ctx,
            tool="repo_apply_patch",
            status="success",
            targets=targets,
            input_bytes=patch_bytes,
            input_hash=patch_hash,
            result_hash=result_hash,
        )

        return {
            "applied": True,
            "targets": targets,
            "branch": diff_result.get("branch", ctx.git.current_branch()),
            "warning": ctx.git.branch_warning(),
            "diff": diff_result.get("diff", ""),
            "truncated": diff_result.get("truncated", False),
            "hidden_files": diff_result.get("hidden_files", 0),
        }
