from __future__ import annotations

import threading
from typing import Any

from audit.logger import AuditLogger
from repo.git import (
    parse_deleted_patch_paths,
    parse_patch_failure_paths,
    reject_unsupported_patch_types,
)
from tools.contracts import ApplyPatchResult
from tools.execution import execute
from tools.runtime import RuntimeContext, audit_event, repository_info

_PATCH_LOCK = threading.Lock()


def _patch_failure_fields(
    state: dict[str, Any],
    exc: BaseException,
) -> dict[str, Any]:
    targets = list(state.get("targets") or [])
    if not targets:
        targets = parse_patch_failure_paths(str(exc))
    fields: dict[str, Any] = {}
    if targets:
        fields["targets"] = targets
    return fields


def register_patch_tools(context: RuntimeContext) -> None:
    @context.mcp.tool()
    def repo_apply_patch(patch: str) -> ApplyPatchResult:
        """Atomically apply one validated unified text patch.

        One patch may contain multiple repository text-file targets. All targets
        are validated before mutation and Git applies the patch as one locked
        operation, so a target failure does not leave a partial multi-file edit.
        """
        patch_bytes = len(patch.encode("utf-8"))
        state: dict[str, Any] = {"targets": []}

        def apply() -> dict[str, Any]:
            if patch_bytes > context.max_patch_bytes:
                raise PermissionError(
                    f"patch exceeds limit: {patch_bytes} > {context.max_patch_bytes}"
                )
            reject_unsupported_patch_types(patch)
            targets = context.git.patch_targets(patch)
            state["targets"] = targets
            deleted = parse_deleted_patch_paths(patch)
            actions = {
                target: ("delete" if target in deleted else "write")
                for target in targets
            }
            for target in targets:
                context.filesystem.check_write_path(target)
            context.scanner.require_clean_patch(patch)
            with _PATCH_LOCK, context.patch_lock:
                if not context.allow_dirty_worktree:
                    conflicts = context.git.conflicting_paths(actions)
                    if conflicts:
                        raise PermissionError(
                            "patch target has existing changes: "
                            + ", ".join(conflicts)
                        )
                context.git.apply_patch_check(patch)
                context.git.apply_patch(patch)

            diff = context.git.diff_for_paths(targets)
            audit_event(
                context,
                event="patch_result",
                status="success",
                targets=targets,
                result_hash=diff["full_hash"],
            )
            return {
                "applied": True,
                "repository": repository_info(context),
                "targets": targets,
                "branch": diff.get("branch", context.git.current_branch()),
                "warning": context.git.branch_warning(),
                "diff": diff.get("diff", ""),
                "truncated": diff.get("truncated", False),
                "result_hash": diff["full_hash"],
                "hidden_files": 0,
            }

        return execute(
            context,
            tool="repo_apply_patch",
            modes=("write", "test"),
            operation=apply,
            input_bytes=patch_bytes,
            input_hash=AuditLogger.hash_value(patch),
            failure_fields=lambda exc: _patch_failure_fields(state, exc),
        )
