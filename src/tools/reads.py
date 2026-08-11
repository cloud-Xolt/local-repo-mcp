from __future__ import annotations

from typing import Any

from repo.search import search_repository
from tools.contracts import (
    GitDiffResult,
    GitStatusResult,
    ListFilesResult,
    ReadFileResult,
    SearchCodeResult,
)
from tools.execution import execute
from tools.runtime import RuntimeContext, repository_info

READ_MODES = ("read", "write", "test")


def register_read_tools(context: RuntimeContext) -> None:
    @context.mcp.tool()
    def repo_list_files(path: str = ".", limit: int = 200) -> ListFilesResult:
        target = path or "."
        result = execute(
            context,
            tool="repo_list_files",
            modes=READ_MODES,
            operation=lambda: context.filesystem.list_files(target, limit),
            target=target,
        )
        result["repository"] = repository_info(context)
        return result

    @context.mcp.tool()
    def repo_read_file(path: str) -> ReadFileResult:
        result = execute(
            context,
            tool="repo_read_file",
            modes=READ_MODES,
            operation=lambda: context.filesystem.read_file(path),
            target=path,
        )
        result["repository"] = repository_info(context)
        return result

    @context.mcp.tool()
    def repo_search_code(query: str, limit: int = 50) -> SearchCodeResult:
        effective_limit = min(max(limit, 1), context.max_search_results)

        def search() -> dict[str, Any]:
            if not query or len(query) > 200:
                raise ValueError(
                    "query is required and must be <= 200 characters"
                )
            return search_repository(
                query,
                context.repo_root,
                effective_limit,
                context.max_output_bytes,
                context.max_file_bytes,
            )

        result = execute(
            context,
            tool="repo_search_code",
            modes=READ_MODES,
            operation=search,
            target=query,
            target_is_sensitive=True,
        )
        result["limit"] = effective_limit
        result["repository"] = repository_info(context)
        return result

    @context.mcp.tool()
    def repo_git_status() -> GitStatusResult:
        result = execute(
            context,
            tool="repo_git_status",
            modes=READ_MODES,
            operation=context.git.status_filtered,
        )
        result["repository"] = repository_info(context)
        return result

    @context.mcp.tool()
    def repo_git_diff(
        staged: bool = False,
        max_bytes: int = 20_000,
    ) -> GitDiffResult:
        result = execute(
            context,
            tool="repo_git_diff",
            modes=READ_MODES,
            operation=lambda: context.git.diff_filtered(
                staged=staged,
                max_bytes=max_bytes,
            ),
            staged=bool(staged),
        )
        result["repository"] = repository_info(context)
        return result
