from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from commands.runner import _safe_temp_root
from tools.tests import _build_test_result, _resolve_image


def test_command_temp_root_never_uses_repository_internal_temp(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    internal_temp = repo / "temp"
    internal_temp.mkdir()
    monkeypatch.setenv("TEMP", str(internal_temp))
    monkeypatch.setenv("TMP", str(internal_temp))

    selected = _safe_temp_root(repo)

    assert not selected.is_relative_to(repo.resolve())
    assert not (internal_temp / "local-repo-mcp-commands").exists()


def test_direct_environment_cannot_raise_image_count_above_hard_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact_root = tmp_path / "test-artifacts"
    artifact_root.mkdir()
    markers: list[str] = []
    for index in range(21):
        image = artifact_root / f"{index}.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\n")
        markers.append(f"MCP_IMAGE:test-artifacts/{index}.png")
    monkeypatch.setenv("MAX_TEST_IMAGES", "999999")

    result = _build_test_result(
        SimpleNamespace(repo_root=tmp_path),  # type: ignore[arg-type]
        {
            "returncode": 0,
            "stdout": "\n".join(markers) + "\n",
            "stderr": "",
        },
    )

    assert len(result.structured_content["images"]) == 20
    assert "MAX_TEST_IMAGES=20" in result.structured_content["image_warnings"][0]


def test_direct_environment_cannot_raise_single_image_limit_above_hard_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact_root = tmp_path / "test-artifacts"
    artifact_root.mkdir()
    image = artifact_root / "large.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + (b"x" * 25))
    monkeypatch.setenv("MAX_TEST_IMAGE_BYTES", "999999")
    monkeypatch.setattr("tools.tests._HARD_MAX_IMAGE_BYTES", 32)

    try:
        _resolve_image(tmp_path, artifact_root, "test-artifacts/large.png")
    except ValueError as exc:
        assert "MAX_TEST_IMAGE_BYTES=32" in str(exc)
    else:
        raise AssertionError("hard image-size limit was not enforced")
