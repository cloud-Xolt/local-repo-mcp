from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult, ImageContent, TextContent

from tools.contracts import VerificationCallToolResult
from tools.execution import execute
from tools.runtime import RuntimeContext, repository_info

_IMAGE_MARKER = "MCP_IMAGE:"
_DEFAULT_ARTIFACT_DIR = "test-artifacts"
_DEFAULT_MAX_IMAGES = 6
_HARD_MAX_IMAGES = 20
_DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_HARD_MAX_IMAGE_BYTES = 8 * 1024 * 1024
_DEFAULT_MAX_TOTAL_IMAGE_BYTES = 2 * 1024 * 1024
_HARD_MAX_TOTAL_IMAGE_BYTES = 8 * 1024 * 1024
_ALLOWED_IMAGE_TYPES = {
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
}


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _positive_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _bounded_positive_int_env(name: str, default: int, maximum: int) -> int:
    return min(_positive_int_env(name, default), maximum)


def _artifact_root(repo_root: Path) -> Path:
    configured = os.environ.get("TEST_ARTIFACT_DIR", _DEFAULT_ARTIFACT_DIR).strip()
    configured_path = Path(configured)
    if not configured or configured_path.is_absolute():
        raise RuntimeError("TEST_ARTIFACT_DIR must be a repository-relative directory")

    root = (repo_root / configured_path).resolve()
    repo = repo_root.resolve()
    if not _is_relative_to(root, repo):
        raise RuntimeError("TEST_ARTIFACT_DIR must stay inside REPO_ROOT")
    return root


def _resolve_image(repo_root: Path, artifact_root: Path, raw_path: str) -> tuple[Path, str]:
    value = raw_path.strip().strip('"').strip("'")
    if not value or "\x00" in value:
        raise ValueError("empty or invalid image path")

    requested = Path(value)
    candidate = requested if requested.is_absolute() else repo_root / requested
    candidate = candidate.resolve(strict=True)

    if not _is_relative_to(candidate, artifact_root):
        raise ValueError("image path is outside the configured test artifact directory")
    if not candidate.is_file():
        raise ValueError("image path is not a regular file")

    image_type = _ALLOWED_IMAGE_TYPES.get(candidate.suffix.lower())
    if image_type is None:
        raise ValueError("only PNG and JPEG screenshots are supported")

    mime_type, signature = image_type
    max_bytes = _bounded_positive_int_env(
        "MAX_TEST_IMAGE_BYTES",
        _DEFAULT_MAX_IMAGE_BYTES,
        _HARD_MAX_IMAGE_BYTES,
    )
    if candidate.stat().st_size > max_bytes:
        raise ValueError(f"image exceeds MAX_TEST_IMAGE_BYTES={max_bytes}")

    with candidate.open("rb") as handle:
        header = handle.read(len(signature))
    if header != signature:
        raise ValueError(f"file signature does not match {mime_type}")

    return candidate, mime_type


def _extract_image_markers(result: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    cleaned = dict(result)
    markers: list[str] = []

    nested = cleaned.get("results")
    if isinstance(nested, list):
        cleaned_results: list[dict[str, Any]] = []
        for item in nested:
            if isinstance(item, dict):
                nested_cleaned, nested_markers = _extract_image_markers(item)
                cleaned_results.append(nested_cleaned)
                markers.extend(nested_markers)
        cleaned["results"] = cleaned_results

    for field in ("stdout", "stderr"):
        value = cleaned.get(field)
        if not isinstance(value, str) or not value:
            continue

        kept_lines: list[str] = []
        for line in value.splitlines(keepends=True):
            stripped = line.strip()
            if stripped.startswith(_IMAGE_MARKER):
                markers.append(stripped[len(_IMAGE_MARKER) :].strip())
                continue
            kept_lines.append(line)
        cleaned[field] = "".join(kept_lines)

    return cleaned, markers


def _result_success(result: dict[str, Any]) -> bool:
    if "success" in result:
        return bool(result["success"])
    code = result.get("returncode")
    return isinstance(code, int) and code == 0


def _format_test_result_text(cleaned: dict[str, Any]) -> str:
    exit_code = cleaned.get("exit_code", cleaned.get("returncode"))
    sections = [
        f"success={cleaned.get('success')}",
        f"exit_code={exit_code}",
        f"command_key={cleaned.get('command_key', '')}",
        f"command={cleaned.get('command', '')}",
        f"status={cleaned.get('status', '')}",
    ]
    stderr = str(cleaned.get("stderr", "")).strip()
    stdout = str(cleaned.get("stdout", "")).strip()
    if stderr:
        sections.extend(["", "stderr:", stderr])
    if stdout:
        sections.extend(["", "stdout:", stdout])
    sections.extend(
        [
            "",
            "structured:",
            json.dumps(cleaned, ensure_ascii=False, indent=2, default=str),
        ]
    )
    return "\n".join(sections)


def _build_test_result(context: RuntimeContext, result: dict[str, Any]) -> CallToolResult:
    cleaned, markers = _extract_image_markers(result)
    artifact_root = _artifact_root(context.repo_root)
    max_images = _bounded_positive_int_env(
        "MAX_TEST_IMAGES",
        _DEFAULT_MAX_IMAGES,
        _HARD_MAX_IMAGES,
    )
    max_total_image_bytes = _bounded_positive_int_env(
        "MAX_TEST_IMAGE_TOTAL_BYTES",
        _DEFAULT_MAX_TOTAL_IMAGE_BYTES,
        _HARD_MAX_TOTAL_IMAGE_BYTES,
    )

    content: list[TextContent | ImageContent] = []
    image_metadata: list[dict[str, Any]] = []
    warnings: list[str] = []
    total_image_bytes = 0

    for index, raw_path in enumerate(markers):
        if index >= max_images:
            warnings.append(f"ignored screenshot {index + 1}: MAX_TEST_IMAGES={max_images}")
            continue
        try:
            image_path, mime_type = _resolve_image(context.repo_root, artifact_root, raw_path)
            image_size = image_path.stat().st_size
            if total_image_bytes + image_size > max_total_image_bytes:
                warnings.append(
                    "ignored screenshot "
                    f"{index + 1}: cumulative image payload would exceed "
                    f"MAX_TEST_IMAGE_TOTAL_BYTES={max_total_image_bytes}"
                )
                continue
            encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
            content.append(ImageContent(type="image", data=encoded, mime_type=mime_type))
            total_image_bytes += image_size
            image_metadata.append(
                {
                    "path": image_path.relative_to(context.repo_root.resolve()).as_posix(),
                    "mime_type": mime_type,
                    "size": image_size,
                }
            )
        except (OSError, RuntimeError, ValueError) as exc:
            warnings.append(f"ignored screenshot {index + 1}: {exc}")

    if image_metadata:
        cleaned["images"] = image_metadata
    if warnings:
        cleaned["image_warnings"] = warnings

    # Keep a readable text result first, then append each image block. The original
    # dictionary is also preserved as structuredContent for existing clients.
    content.insert(
        0,
        TextContent(
            type="text",
            text=_format_test_result_text(cleaned),
        ),
    )

    # Non-zero exit codes are command failures, not MCP tool failures. Clients such
    # as ChatGPT discard tool bodies when is_error=True, so always return evidence
    # in content/structured_content and encode pass/fail in the payload itself.
    return CallToolResult(
        content=content,
        structured_content=cleaned,
        is_error=False,
    )


def _requested_command_keys(
    command_key: str,
    command_keys: list[str] | None,
) -> tuple[list[str], bool]:
    single = command_key.strip()
    batch = [str(item).strip() for item in (command_keys or [])]
    if single and batch:
        raise ValueError("use command_key for one command or command_keys for a batch, not both")
    if batch:
        if any(not item for item in batch):
            raise ValueError("command_keys cannot contain empty values")
        return batch, True
    if single:
        return [single], False
    raise ValueError("command_key or command_keys is required")


def register_test_tools(context: RuntimeContext) -> None:
    @context.mcp.tool()
    def repo_run_test(
        command_key: str = "",
        command_keys: tuple[str, ...] = (),
        timeout_seconds: int = 120,
        stop_on_failure: bool = True,
    ) -> VerificationCallToolResult:
        """Run one or more allowlisted repository verification commands.

        The allowlist covers test/build/lint/check profiles for common Python,
        Go, Node, Maven, and Gradle repositories. `command_key` preserves the
        original single-command API. `command_keys` runs a bounded sequential
        batch; the complete batch is validated before the first command starts.

        Every started command returns command, exit_code, stdout, stderr,
        duration and truncation metadata. Timeout/output-limit termination is a
        structured failed result so captured evidence is not discarded.

        Commands may emit `MCP_IMAGE:<repository-relative-path>` lines for
        PNG/JPEG files under the configured test artifact directory; screenshots
        are returned as native MCP image content.
        """

        def run_requested() -> dict[str, Any]:
            keys, is_batch = _requested_command_keys(command_key, command_keys)
            if is_batch:
                return context.command_runner.run_many(
                    keys,
                    timeout_seconds,
                    stop_on_failure=stop_on_failure,
                ).as_dict()
            return context.command_runner.run(keys[0], timeout_seconds).as_dict()

        result = execute(
            context,
            tool="repo_run_test",
            modes=("test",),
            operation=run_requested,
            result_status=lambda value: (
                "success" if _result_success(value) else "failed"
            ),
            command_key=command_key,
            command_keys=command_keys or [],
            repository_root=str(context.repo_root.resolve()),
        )
        result["repository"] = repository_info(context)
        return _build_test_result(context, result)
