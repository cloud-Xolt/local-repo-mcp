from commands.models import CommandBatchResult, CommandResult, CommandSpec


def test_batch_result_reports_requested_remaining_and_duration() -> None:
    ok = CommandResult(
        spec=CommandSpec("one", "test", ("tool", "one")),
        status="success",
        exit_code=0,
        stdout="",
        stderr="",
        stdout_truncated=False,
        stderr_truncated=False,
        timeout_seconds=10,
        duration_ms=7,
    )
    payload = CommandBatchResult(
        requested=("one", "two"), results=(ok,), stop_on_failure=True
    ).as_dict()
    assert payload["requested"] == ["one", "two"]
    assert payload["remaining"] == ["two"]
    assert payload["duration_ms"] == 7
