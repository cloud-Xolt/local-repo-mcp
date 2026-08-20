from __future__ import annotations

from typing import Annotated, Literal, NotRequired, TypedDict

from mcp.types import CallToolResult
from pydantic import BaseModel, ConfigDict

EXPECTED_TOOL_NAMES = frozenset(
    {
        "repo_list_files",
        "repo_read_file",
        "repo_search_code",
        "repo_git_status",
        "repo_git_diff",
        "repo_apply_patch",
        "repo_git_commit",
        "repo_run_test",
    }
)


class RepositoryRef(TypedDict):
    name: str
    root: str


class ListFilesResult(TypedDict):
    files: list[str]
    truncated: bool
    limit: int
    repository: RepositoryRef


class ReadFileResult(TypedDict):
    path: str
    bytes: int
    content_type: Literal["text", "image"]
    content_trust: Literal["untrusted_repository_data"]
    repository: RepositoryRef
    content: NotRequired[str]
    mime_type: NotRequired[Literal["image/png", "image/jpeg"]]
    content_base64: NotRequired[str]


class ReadFileResultModel(BaseModel):
    """Wire contract for repo_read_file structuredContent."""

    model_config = ConfigDict(extra="allow")

    path: str
    bytes: int
    content_type: Literal["text", "image"]
    content_trust: Literal["untrusted_repository_data"]
    repository: RepositoryRef
    content: str | None = None
    mime_type: Literal["image/png", "image/jpeg"] | None = None
    content_base64: str | None = None


ReadFileCallToolResult = Annotated[CallToolResult, ReadFileResultModel]


class SearchMatch(TypedDict):
    path: str
    line: int | None
    text: str


class SearchCodeResult(TypedDict):
    matches: list[SearchMatch]
    truncated: bool
    backend: Literal["ripgrep", "python"]
    limit: int
    repository: RepositoryRef


class GitStatusEntry(TypedDict):
    status: str
    path: str


class GitStatusResult(TypedDict):
    branch: str
    entries: list[GitStatusEntry]
    hidden_entries: int
    repository: RepositoryRef


class GitDiffResult(TypedDict):
    diff: str
    hidden_files: int
    truncated: bool
    branch: str
    repository: RepositoryRef


class ApplyPatchResult(TypedDict):
    applied: bool
    repository: RepositoryRef
    targets: list[str]
    branch: str
    warning: str | None
    diff: str
    truncated: bool
    result_hash: str
    hidden_files: int


class GitCommitResult(TypedDict):
    committed: bool
    commit: str
    branch: str
    paths: list[str]
    message: str
    warning: str | None
    hidden_paths: int
    repository: RepositoryRef


class ImageMetadata(TypedDict):
    path: str
    mime_type: Literal["image/png", "image/jpeg"]
    size: int


class CommandEvidence(TypedDict):
    command_key: str
    command_kind: Literal["test", "build", "lint", "check"]
    argv: list[str]
    command: str
    status: Literal["success", "failed", "timeout", "output_limit"]
    success: bool
    exit_code: int | None
    returncode: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    timeout_seconds: int
    duration_ms: int


class VerificationResultModel(BaseModel):
    """Wire contract for repo_run_test structuredContent.

    The command tool has two result shapes (single and bounded batch) and may
    attach image metadata. Common fields are explicit while mode-specific fields
    remain optional. Extra fields stay allowed so the execution layer can evolve
    evidence without silently dropping data from direct CallToolResult responses.
    """

    model_config = ConfigDict(extra="allow")

    status: Literal["success", "failed", "timeout", "output_limit"]
    success: bool
    repository: RepositoryRef
    batch: bool | None = None
    command_key: str | None = None
    command_kind: Literal["test", "build", "lint", "check"] | None = None
    working_dir: str | None = None
    argv: list[str] | None = None
    command: str | None = None
    exit_code: int | None = None
    returncode: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    stdout_truncated: bool | None = None
    stderr_truncated: bool | None = None
    timeout_seconds: int | None = None
    duration_ms: int
    requested_count: int | None = None
    completed_count: int | None = None
    stop_on_failure: bool | None = None
    requested: list[str] | None = None
    remaining: list[str] | None = None
    results: list[CommandEvidence] | None = None
    images: list[ImageMetadata] | None = None
    image_warnings: list[str] | None = None


VerificationCallToolResult = Annotated[CallToolResult, VerificationResultModel]


def schema_value(tool: object, snake_name: str, camel_name: str):
    """Read an MCP schema field across SDK/client naming conventions."""

    value = getattr(tool, snake_name, None)
    if value is not None:
        return value
    return getattr(tool, camel_name, None)


def contract_problems(tools: list[object]) -> list[str]:
    """Return protocol-level contract problems visible to MCP clients."""

    problems: list[str] = []
    names = {str(getattr(tool, "name", "")) for tool in tools}
    if names != EXPECTED_TOOL_NAMES:
        missing = sorted(EXPECTED_TOOL_NAMES - names)
        extra = sorted(names - EXPECTED_TOOL_NAMES)
        if missing:
            problems.append("missing tools: " + ", ".join(missing))
        if extra:
            problems.append("unexpected tools: " + ", ".join(extra))

    for tool in tools:
        name = str(getattr(tool, "name", "<unknown>"))
        input_schema = schema_value(tool, "input_schema", "inputSchema")
        output_schema = schema_value(tool, "output_schema", "outputSchema")
        if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
            problems.append(f"{name}: invalid input schema")
        if not isinstance(output_schema, dict) or output_schema.get("type") != "object":
            problems.append(f"{name}: missing or invalid output schema")
        elif not isinstance(output_schema.get("properties"), dict) or not output_schema["properties"]:
            problems.append(f"{name}: output schema has no properties")

    return problems
