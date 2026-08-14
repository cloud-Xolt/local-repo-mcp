from __future__ import annotations

from typing import Any

from repo.file_scope import TraversalOptions
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


def _normalize_patterns(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    patterns: list[str] = []
    seen: set[str] = set()
    for raw in values:
        pattern = raw.replace("\\", "/").strip()
        if not pattern or pattern in seen:
            continue
        seen.add(pattern)
        patterns.append(pattern)
        if len(patterns) >= 50:
            break
    return tuple(patterns)


def _scope_audit_fields(options: TraversalOptions, *, limit: int | None = None) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "respect_gitignore": options.respect_gitignore,
        "max_file_bytes": options.max_file_bytes,
    }
    if limit is not None:
        fields["limit"] = limit
    if options.include:
        fields["include"] = list(options.include)
    if options.exclude:
        fields["exclude"] = list(options.exclude)
    return fields


def _traversal_options(
    context: RuntimeContext,
    *,
    path: str = ".",
    limit: int | None,
    include: list[str] | None,
    exclude: list[str] | None,
    respect_gitignore: bool,
    max_file_size: int | None,
) -> TraversalOptions:
    configured_max = context.max_file_bytes
    if max_file_size is not None:
        if max_file_size <= 0:
            raise ValueError("max_file_size must be greater than zero")
        effective_max = min(max_file_size, configured_max)
    else:
        effective_max = configured_max
    return TraversalOptions(
        path=path or ".",
        limit=limit,
        include=_normalize_patterns(include),
        exclude=_normalize_patterns(exclude),
        respect_gitignore=respect_gitignore,
        max_file_bytes=effective_max,
    )


def register_read_tools(context: RuntimeContext) -> None:
    @context.mcp.tool()
    def repo_list_files(
        path: str = ".",
        limit: int = 200,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        respect_gitignore: bool = True,
        max_file_size: int | None = None,
    ) -> ListFilesResult:
        target = path or "."
        options = _traversal_options(
            context,
            path=target,
            limit=limit,
            include=include,
            exclude=exclude,
            respect_gitignore=respect_gitignore,
            max_file_size=max_file_size,
        )

        def operation() -> dict[str, Any]:
            return context.filesystem.list_files(options)

        result = execute(
            context,
            tool="repo_list_files",
            modes=READ_MODES,
            operation=operation,
            target=target,
            **_scope_audit_fields(options, limit=limit),
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
    def repo_search_code(
        query: str,
        limit: int = 50,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        respect_gitignore: bool = True,
        max_file_size: int | None = None,
    ) -> SearchCodeResult:
        effective_limit = min(max(limit, 1), context.max_search_results)
        options = _traversal_options(
            context,
            path=".",
            limit=None,
            include=include,
            exclude=exclude,
            respect_gitignore=respect_gitignore,
            max_file_size=max_file_size,
        )

        def search() -> dict[str, Any]:
            if not query or len(query) > 200:
                raise ValueError(
                    "query is required and must be <= 200 characters"
                )
            return search_repository(
                query,
                context.repo_root,
                options,
                context.max_output_bytes,
                effective_limit,
                scope=context.filesystem.scope,
            )

        result = execute(
            context,
            tool="repo_search_code",
            modes=READ_MODES,
            operation=search,
            target=query,
            target_is_sensitive=True,
            **_scope_audit_fields(options, limit=effective_limit),
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
