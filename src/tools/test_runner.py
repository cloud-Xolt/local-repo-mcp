from __future__ import annotations

from pathlib import Path


# Backward-compatible facade: execution is delegated to the command layer.
from commands.registry import DEFAULT_COMMAND_REGISTRY as _COMMAND_REGISTRY
from commands.runner import RepoCommandRunner as _RepoCommandRunner

TEST_COMMANDS = {
    key: list(_COMMAND_REGISTRY.get(key).argv) for key in _COMMAND_REGISTRY.keys()
}


class RepoTestRunner:
    def __init__(self, repo_root: Path, max_output_bytes: int, max_timeout: int) -> None:
        self._runner = _RepoCommandRunner(repo_root, max_output_bytes, max_timeout)

    @property
    def event_sink(self):
        return self._runner.event_sink

    @event_sink.setter
    def event_sink(self, value) -> None:
        self._runner.event_sink = value

    def run(
        self,
        command_key: str,
        timeout_seconds: int,
        *,
        working_dir: str = ".",
    ) -> dict:
        return self._runner.run(
            command_key,
            timeout_seconds,
            working_dir=working_dir,
        ).as_dict()

    def run_many(
        self,
        command_keys: list[str],
        timeout_seconds: int,
        *,
        stop_on_failure: bool = True,
        working_dir: str = ".",
    ) -> dict:
        return self._runner.run_many(
            command_keys,
            timeout_seconds,
            stop_on_failure=stop_on_failure,
            working_dir=working_dir,
        ).as_dict()
