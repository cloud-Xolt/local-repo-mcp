from pathlib import Path

import pytest

from tools.test_runner import RepoTestRunner


def test_rejects_arbitrary_command(tmp_path: Path) -> None:
    runner = RepoTestRunner(tmp_path, 20000, 300)
    with pytest.raises(PermissionError):
        runner.run("rm -rf /", 10)


def test_output_is_bounded() -> None:
    from tools.test_runner import _truncate

    text, truncated = _truncate("x" * 100, 10)
    assert truncated is True
    assert len(text.encode()) <= 10
