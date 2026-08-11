from __future__ import annotations

from pathlib import Path

from tools.tests import _build_test_result
from test_test_image_content import FakeContext


def test_total_native_image_payload_is_bounded(tmp_path: Path, monkeypatch) -> None:
    artifact_root = tmp_path / "test-artifacts"
    artifact_root.mkdir()
    first = artifact_root / "first.png"
    second = artifact_root / "second.png"
    payload = b"\x89PNG\r\n\x1a\n" + (b"x" * 700_000)
    first.write_bytes(payload)
    second.write_bytes(payload)
    monkeypatch.setenv("MAX_TEST_IMAGE_TOTAL_BYTES", "1000000")

    result = _build_test_result(
        FakeContext(tmp_path),  # type: ignore[arg-type]
        {
            "returncode": 0,
            "stdout": "MCP_IMAGE:test-artifacts/first.png\nMCP_IMAGE:test-artifacts/second.png\n",
            "stderr": "",
        },
    )

    assert len(result.content) == 2
    assert len(result.structured_content["images"]) == 1
    assert "MAX_TEST_IMAGE_TOTAL_BYTES=1000000" in result.structured_content["image_warnings"][0]
