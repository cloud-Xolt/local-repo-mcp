from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.tests import _build_test_result, _extract_image_markers, _resolve_image


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-png-payload"
JPEG_BYTES = b"\xff\xd8\xff" + b"test-jpeg-payload"


@dataclass
class FakeContext:
    repo_root: Path


def test_extracts_markers_from_stdout_and_stderr() -> None:
    cleaned, markers = _extract_image_markers(
        {
            "returncode": 0,
            "stdout": "before\nMCP_IMAGE:test-artifacts/a.png\nafter\n",
            "stderr": "MCP_IMAGE:test-artifacts/b.jpg\nwarning\n",
        }
    )

    assert markers == ["test-artifacts/a.png", "test-artifacts/b.jpg"]
    assert cleaned["stdout"] == "before\nafter\n"
    assert cleaned["stderr"] == "warning\n"


def test_resolves_png_inside_artifact_root(tmp_path: Path) -> None:
    artifact_root = tmp_path / "test-artifacts"
    artifact_root.mkdir()
    image = artifact_root / "screen.png"
    image.write_bytes(PNG_BYTES)

    resolved, mime_type = _resolve_image(
        tmp_path,
        artifact_root.resolve(),
        "test-artifacts/screen.png",
    )

    assert resolved == image.resolve()
    assert mime_type == "image/png"


def test_rejects_path_outside_artifact_root(tmp_path: Path) -> None:
    artifact_root = tmp_path / "test-artifacts"
    artifact_root.mkdir()
    outside = tmp_path / "secret.png"
    outside.write_bytes(PNG_BYTES)

    with pytest.raises(ValueError, match="outside"):
        _resolve_image(tmp_path, artifact_root.resolve(), "secret.png")


def test_rejects_fake_png(tmp_path: Path) -> None:
    artifact_root = tmp_path / "test-artifacts"
    artifact_root.mkdir()
    image = artifact_root / "fake.png"
    image.write_bytes(b"not a png")

    with pytest.raises(ValueError, match="signature"):
        _resolve_image(
            tmp_path,
            artifact_root.resolve(),
            "test-artifacts/fake.png",
        )


def test_returns_text_and_native_image_content(tmp_path: Path) -> None:
    artifact_root = tmp_path / "test-artifacts"
    artifact_root.mkdir()
    image = artifact_root / "mobile.png"
    image.write_bytes(PNG_BYTES)

    result = _build_test_result(
        FakeContext(tmp_path),  # type: ignore[arg-type]
        {
            "returncode": 0,
            "stdout": "ok\nMCP_IMAGE:test-artifacts/mobile.png\n",
            "stderr": "",
        },
    )

    assert result.is_error is False
    assert result.content[0].type == "text"
    assert result.content[1].type == "image"
    assert result.content[1].mime_type == "image/png"
    assert result.structured_content["images"][0]["path"] == "test-artifacts/mobile.png"


def test_invalid_marker_is_reported_without_exposing_file(tmp_path: Path) -> None:
    (tmp_path / "test-artifacts").mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(JPEG_BYTES)

    result = _build_test_result(
        FakeContext(tmp_path),  # type: ignore[arg-type]
        {
            "returncode": 0,
            "stdout": "MCP_IMAGE:outside.jpg\n",
            "stderr": "",
        },
    )

    assert len(result.content) == 1
    assert "image_warnings" in result.structured_content
