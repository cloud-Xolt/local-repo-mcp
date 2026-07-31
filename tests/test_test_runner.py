import pytest

from tools.context import require_mode
from tools.test_runner import RepoTestRunner, TEST_COMMANDS


def test_read_mode_rejects_test(runtime, monkeypatch) -> None:
    runtime.mode = "read"
    with pytest.raises(PermissionError):
        require_mode(runtime, "test")


def test_write_mode_rejects_test(runtime, monkeypatch) -> None:
    runtime.mode = "write"
    with pytest.raises(PermissionError):
        require_mode(runtime, "test")


def test_unknown_command_key(runtime) -> None:
    runner = RepoTestRunner(runtime.repo_root)
    with pytest.raises(PermissionError):
        runner.run("custom_shell", 5)


def test_whitelist_keys_exist() -> None:
    assert "python_pytest" in TEST_COMMANDS
    for command in TEST_COMMANDS.values():
        assert isinstance(command, list)
        assert command
