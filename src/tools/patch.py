from __future__ import annotations

import threading
from typing import Any

from audit.logger import AuditLogger
from repo.git import parse_deleted_patch_paths, reject_unsupported_patch_types
from tools.context import RuntimeContext, audit_event, repository_info, require_mode

_PATCH_LOCK = threading.Lock()


def register_patch_tools(ctx: RuntimeContext) -> None:
    @ctx.mcp.tool()
    def repo_apply_patch(patch: str) -> dict[str, Any]:
        """Apply one validated unified text patch to the configured repository.

        Unrelated worktree changes do not block this operation. Existing changes
        on files targeted by the patch are protected by default.
        """
        require_mode(ctx, "write", "test")
        patch_bytes = len(patch.encode("utf-8"))
        if patch_bytes > ctx.max_patch_bytes:
            raise PermissionError(f"patch exceeds limit: {patch_bytes} > {ctx.max_patch_bytes}")

        reject_unsupported_patch_types(patch)
        targets = ctx.git.patch_targets(patch)
        deleted = parse_deleted_patch_paths(patch)
        actions = {target: ("delete" if target in deleted else "write") for target in targets}

        for target in targets:
            ctx.filesystem.check_write_path(target)
        ctx.scanner.require_clean_patch(patch)

        try:
            with _PATCH_LOCK:
                if not ctx.allow_dirty_worktree:
                    conflicts = ctx.git.conflicting_paths(actions)
                    if conflicts:
                        raise PermissionError("patch target has existing changes: " + ", ".join(conflicts))
                ctx.git.apply_patch_check(patch)
                ctx.git.apply_patch(patch)
        except Exception as exc:
            audit_event(
                ctx,
                tool="repo_apply_patch",
                status="failed",
                targets=targets,
                input_bytes=patch_bytes,
                input_hash=AuditLogger.hash_value(patch),
                error_type=type(exc).__name__,
            )
            raise

        diff = ctx.git.diff_filtered(staged=False)
        audit_event(
            ctx,
            tool="repo_apply_patch",
            status="success",
            targets=targets,
            input_bytes=patch_bytes,
            input_hash=AuditLogger.hash_value(patch),
            result_hash=AuditLogger.hash_value(diff.get("diff", "")),
        )
        return {
            "applied": True,
            "repository": repository_info(ctx),
            "targets": targets,
            "branch": diff.get("branch", ctx.git.current_branch()),
            "warning": ctx.git.branch_warning(),
            "diff": diff.get("diff", ""),
            "truncated": diff.get("truncated", False),
            "hidden_files": diff.get("hidden_files", 0),
        }
