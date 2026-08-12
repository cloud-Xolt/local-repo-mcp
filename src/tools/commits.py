from __future__ import annotations

from typing import Any

from tools.contracts import GitCommitResult
from tools.execution import execute
from tools.runtime import RuntimeContext, repository_info


def register_commit_tools(context: RuntimeContext) -> None:
    @context.mcp.tool()
    def repo_git_commit(
        message: str,
        paths: list[str] | None = None,
    ) -> GitCommitResult:
        """Create one local Git commit for allowlisted pending changes.

        Disabled unless ALLOW_GIT_COMMIT is enabled (GUI: allow Git commit).
        Requires write or test mode. Does not push, amend, reset, rebase,
        checkout, or skip hooks. Sensitive paths are never staged.
        """

        def commit() -> dict[str, Any]:
            if not context.allow_git_commit:
                raise PermissionError(
                    "git commit is disabled; enable allow_git_commit in the GUI "
                    "or set ALLOW_GIT_COMMIT=true"
                )
            with context.patch_lock:
                result = context.git.commit_paths(message, paths)
            result["repository"] = repository_info(context)
            return result

        return execute(
            context,
            tool="repo_git_commit",
            modes=("write", "test"),
            operation=commit,
            target=(message or "")[:120],
            target_is_sensitive=True,
        )
