from __future__ import annotations

from pathlib import Path

import pytest

from tools.test_runner import RepoTestRunner, _read_bounded, _safe_environment


def test_rejects_arbitrary_command(tmp_path: Path) -> None:
    runner = RepoTestRunner(tmp_path, 20_000, 300)
    with pytest.raises(PermissionError, match="allowed="):
        runner.run("rm -rf /", 10)


def test_output_is_bounded(tmp_path: Path) -> None:
    output = tmp_path / "output.log"
    output.write_text("x" * 100, encoding="utf-8")
    text, truncated = _read_bounded(output, 10)
    assert truncated is True
    assert len(text.encode()) <= 10


def test_unexpanded_windows_values_are_removed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("APPDATA", "%SystemDrive%\\broken")
    monkeypatch.setenv("TEMP", "%SystemDrive%\\broken")
    env = _safe_environment(tmp_path)
    assert "%SystemDrive%" not in env.get("APPDATA", "")
    assert "%SystemDrive%" not in env["TEMP"]
    assert Path(env["TEMP"]).is_absolute()
