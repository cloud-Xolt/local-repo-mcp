from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult, ImageContent, TextContent

from tools.execution import execute
from tools.runtime import RuntimeContext, repository_info

_IMAGE_MARKER = "MCP_IMAGE:"
_DEFAULT_ARTIFACT_DIR = "test-artifacts"
_DEFAULT_MAX_IMAGES = 6
_DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024
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
    max_bytes = _positive_int_env("MAX_TEST_IMAGE_BYTES", _DEFAULT_MAX_IMAGE_BYTES)
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


def _build_test_result(context: RuntimeContext, result: dict[str, Any]) -> CallToolResult:
    cleaned, markers = _extract_image_markers(result)
    artifact_root = _artifact_root(context.repo_root)
    max_images = _positive_int_env("MAX_TEST_IMAGES", _DEFAULT_MAX_IMAGES)

    content: list[TextContent | ImageContent] = []
    image_metadata: list[dict[str, Any]] = []
    warnings: list[str] = []

    for index, raw_path in enumerate(markers):
        if index >= max_images:
            warnings.append(f"ignored screenshot {index + 1}: MAX_TEST_IMAGES={max_images}")
            continue
        try:
            image_path, mime_type = _resolve_image(context.repo_root, artifact_root, raw_path)
            encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
            content.append(ImageContent(type="image", data=encoded, mime_type=mime_type))
            image_metadata.append(
                {
                    "path": image_path.relative_to(context.repo_root.resolve()).as_posix(),
                    "mime_type": mime_type,
                    "size": image_path.stat().st_size,
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
            text=json.dumps(cleaned, ensure_ascii=False, indent=2, default=str),
        ),
    )

    return CallToolResult(
        content=content,
        structured_content=cleaned,
        is_error=int(result.get("returncode", 1)) != 0,
    )


def register_test_tools(context: RuntimeContext) -> None:
    @context.mcp.tool()
    def repo_run_test(
        command_key: str,
        timeout_seconds: int = 120,
    ) -> CallToolResult:
        """Run an allowlisted repository test command.

        Supported keys are python_pytest, go_test, node_test, node_lint,
        maven_test, and gradle_test. Test mode grants access to this tool;
        the command key remains independently constrained by policy.

        Test commands may emit `MCP_IMAGE:<repository-relative-path>` lines for
        PNG/JPEG files under `test-artifacts/`; those screenshots are returned as
        native MCP image content alongside the normal structured test result.
        """
        result = execute(
            context,
            tool="repo_run_test",
            modes=("test",),
            operation=lambda: context.test_runner.run(
                command_key,
                timeout_seconds,
            ),
            result_status=lambda value: (
                "success" if int(value.get("returncode", 1)) == 0 else "failed"
            ),
            command_key=command_key,
        )
        result["repository"] = repository_info(context)
        return _build_test_result(context, result)
