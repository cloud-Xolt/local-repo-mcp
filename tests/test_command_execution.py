from __future__ import annotations

import sys
from pathlib import Path

import pytest

from commands.models import CommandSpec
from commands.registry import DEFAULT_COMMAND_REGISTRY, CommandRegistry
from commands.runner import RepoCommandRunner, _safe_environment
from tools.test_runner import RepoTestRunner
from tools.tests import _extract_image_markers, _requested_command_keys


def _registry(*specs: CommandSpec) -> CommandRegistry:
    return CommandRegistry(specs)


def _python_spec(key: str, code: str, kind: str = "test") -> CommandSpec:
    return CommandSpec(key, kind, (sys.executable, "-c", code))  # type: ignore[arg-type]


def test_default_registry_covers_test_build_lint_and_check() -> None:
    keys = set(DEFAULT_COMMAND_REGISTRY.keys())
    assert {
        "python_pytest",
        "go_test",
        "go_build",
        "go_vet",
        "go_fmt",
        "node_test",
        "node_build",
        "node_lint",
        "maven_test",
        "maven_build",
        "gradle_test",
        "gradle_build",
    } <= keys
    assert DEFAULT_COMMAND_REGISTRY.get("go_build").kind == "build"
    assert DEFAULT_COMMAND_REGISTRY.get("go_vet").kind == "check"


def test_runner_rejects_unbounded_resource_configuration(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_output_bytes"):
        RepoCommandRunner(tmp_path, 0, 30)
    with pytest.raises(ValueError, match="max_timeout"):
        RepoCommandRunner(tmp_path, 20_000, 0)

    runner = RepoCommandRunner(tmp_path, 20_000, 30, max_batch_commands=99)
    assert runner.max_batch_commands == 8


def test_go_commands_fail_fast_without_go_mod(tmp_path: Path) -> None:
    runner = RepoCommandRunner(tmp_path, 20_000, 30)
    result = runner.run("go_test", 10).as_dict()

    assert result["success"] is False
    assert result["exit_code"] == 1
    assert "missing required go.mod" in result["stderr"]


def test_runner_uses_subdirectory_working_dir(tmp_path: Path) -> None:
    sub = tmp_path / "backend"
    sub.mkdir()
    runner = RepoCommandRunner(
        tmp_path,
        20_000,
        30,
        registry=_registry(_python_spec("cwd", "import os; print(os.getcwd())")),
    )

    result = runner.run("cwd", 10, working_dir="backend").as_dict()

    assert result["working_dir"] == "backend"
    assert Path(result["stdout"].strip()) == sub.resolve()


def test_go_preflight_checks_subdirectory_working_dir(tmp_path: Path) -> None:
    sub = tmp_path / "backend"
    sub.mkdir()
    runner = RepoCommandRunner(tmp_path, 20_000, 30)

    missing = runner.run("go_test", 10, working_dir="backend").as_dict()
    assert "missing required go.mod" in missing["stderr"]

    (sub / "go.mod").write_text("module example.com/backend\n\ngo 1.21\n", encoding="utf-8")
    ready = runner.run("go_test", 10, working_dir="backend").as_dict()
    assert "missing required go.mod" not in ready["stderr"]


def test_preflight_is_language_agnostic_for_working_dir(tmp_path: Path) -> None:
    web = tmp_path / "packages" / "web"
    web.mkdir(parents=True)
    (web / "package.json").write_text('{"name":"web"}\n', encoding="utf-8")
    runner = RepoCommandRunner(
        tmp_path,
        20_000,
        30,
        registry=_registry(_python_spec("node_test", "print('ok')")),
    )

    blocked = runner.run("node_test", 10).as_dict()
    assert "missing required package.json" in blocked["stderr"]

    allowed = runner.run("node_test", 10, working_dir="packages/web").as_dict()
    assert "missing required package.json" not in allowed["stderr"]
    assert allowed["working_dir"] == "packages/web"


def test_unknown_command_key_hints_working_dir_instead_of_prefix_aliases() -> None:
    with pytest.raises(PermissionError, match="working_dir"):
        DEFAULT_COMMAND_REGISTRY.get("backend_go_test")


def test_runner_rejects_invalid_working_dir(tmp_path: Path) -> None:
    runner = RepoCommandRunner(
        tmp_path,
        20_000,
        30,
        registry=_registry(_python_spec("ok", "print('ok')")),
    )
    with pytest.raises(PermissionError, match="parent traversal"):
        runner.run("ok", 10, working_dir="../outside")
    with pytest.raises(NotADirectoryError, match="not a directory"):
        runner.run("ok", 10, working_dir="missing")
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError, match="not a directory"):
        runner.run("ok", 10, working_dir="file.txt")


def test_safe_environment_preserves_go_toolchain_vars(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOMODCACHE", "C:/Users/test/go/pkg/mod")
    monkeypatch.setenv("GOPROXY", "https://proxy.example")
    monkeypatch.setenv("SECRET_TOKEN", "must-not-leak")
    env = _safe_environment(tmp_path)
    assert env["GOMODCACHE"] == "C:/Users/test/go/pkg/mod"
    assert env["GOPROXY"] == "https://proxy.example"
    assert "SECRET_TOKEN" not in env
    assert "-buildvcs=false" in env["GOFLAGS"]


def test_safe_environment_appends_buildvcs_without_clobbering_goflags(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("GOFLAGS", "-tags=integration")
    env = _safe_environment(tmp_path)
    assert "-tags=integration" in env["GOFLAGS"]
    assert "-buildvcs=false" in env["GOFLAGS"]


def test_single_command_returns_verifiable_evidence(tmp_path: Path) -> None:
    events: list[dict] = []
    runner = RepoCommandRunner(
        tmp_path,
        20_000,
        30,
        registry=_registry(_python_spec("ok", "print('verified')")),
        event_sink=events.append,
    )
    result = runner.run("ok", 10)
    payload = result.as_dict()

    assert payload["success"] is True
    assert payload["status"] == "success"
    assert payload["exit_code"] == payload["returncode"] == 0
    assert payload["command_key"] == "ok"
    assert payload["command_kind"] == "test"
    assert "verified" in payload["stdout"]
    assert payload["stderr"] == ""
    assert isinstance(payload["duration_ms"], int)
    assert [event["event"] for event in events] == [
        "command_start",
        "command_finish",
    ]
    assert all("stdout" not in event for event in events)
    assert all("stderr" not in event for event in events)


def test_timeout_is_structured_and_preserves_partial_output(tmp_path: Path) -> None:
    runner = RepoCommandRunner(
        tmp_path,
        20_000,
        30,
        registry=_registry(
            _python_spec(
                "slow",
                "import time; print('before-timeout', flush=True); time.sleep(5)",
            )
        ),
    )

    result = runner.run("slow", 1).as_dict()

    assert result["success"] is False
    assert result["status"] == "timeout"
    assert "before-timeout" in result["stdout"]
    assert isinstance(result["exit_code"], int)
    assert result["duration_ms"] >= 900


def test_batch_is_fully_allowlist_validated_before_execution(tmp_path: Path) -> None:
    marker = tmp_path / "should-not-exist.txt"
    code = "from pathlib import Path; Path('should-not-exist.txt').write_text('ran')"
    runner = RepoCommandRunner(
        tmp_path,
        20_000,
        30,
        registry=_registry(_python_spec("first", code)),
    )

    with pytest.raises(PermissionError, match="not allowed"):
        runner.run_many(["first", "missing"], 10)

    assert not marker.exists()


def test_batch_stop_on_failure_and_continue_modes(tmp_path: Path) -> None:
    registry = _registry(
        _python_spec("one", "print('one')"),
        _python_spec("fail", "import sys; print('bad', file=sys.stderr); sys.exit(3)"),
        _python_spec("two", "print('two')"),
    )
    runner = RepoCommandRunner(tmp_path, 20_000, 30, registry=registry)

    stopped = runner.run_many(["one", "fail", "two"], 10).as_dict()
    assert stopped["success"] is False
    assert stopped["completed_count"] == 2
    assert [item["command_key"] for item in stopped["results"]] == ["one", "fail"]
    assert stopped["results"][1]["exit_code"] == 3

    continued = runner.run_many(
        ["one", "fail", "two"],
        10,
        stop_on_failure=False,
    ).as_dict()
    assert continued["success"] is False
    assert continued["completed_count"] == 3
    assert continued["results"][2]["success"] is True


def test_batch_rejects_duplicates_and_limit_before_execution(tmp_path: Path) -> None:
    registry = _registry(*[
        _python_spec(f"cmd{index}", "print('ok')")
        for index in range(9)
    ])
    runner = RepoCommandRunner(
        tmp_path,
        20_000,
        30,
        registry=registry,
        max_batch_commands=20,
    )

    with pytest.raises(ValueError, match="duplicate"):
        runner.run_many(["cmd0", "cmd0"], 10)
    with pytest.raises(PermissionError, match="batch exceeds"):
        runner.run_many([f"cmd{index}" for index in range(9)], 10)


def test_legacy_runner_delegates_single_and_batch_to_command_layer(tmp_path: Path) -> None:
    runner = RepoTestRunner(tmp_path, 20_000, 30)
    assert "go_build" in runner._runner.registry.keys()
    assert callable(runner.run_many)


def test_mcp_command_selection_preserves_single_and_batch_compatibility() -> None:
    assert _requested_command_keys("go_test", None) == (["go_test"], False)
    assert _requested_command_keys("", ["go_test", "go_build"]) == (
        ["go_test", "go_build"],
        True,
    )
    with pytest.raises(ValueError, match="not both"):
        _requested_command_keys("go_test", ["go_build"])
    with pytest.raises(ValueError, match="required"):
        _requested_command_keys("", None)


def test_batch_image_markers_are_extracted_per_command() -> None:
    cleaned, markers = _extract_image_markers(
        {
            "success": True,
            "results": [
                {
                    "stdout": "one\nMCP_IMAGE:test-artifacts/one.png\n",
                    "stderr": "",
                },
                {
                    "stdout": "",
                    "stderr": "MCP_IMAGE:test-artifacts/two.jpg\nwarning\n",
                },
            ],
        }
    )

    assert markers == [
        "test-artifacts/one.png",
        "test-artifacts/two.jpg",
    ]
    assert "MCP_IMAGE:" not in cleaned["results"][0]["stdout"]
    assert cleaned["results"][1]["stderr"] == "warning\n"


def test_command_start_log_failure_terminates_child(tmp_path: Path) -> None:
    marker = tmp_path / "orphan-marker.txt"
    code = (
        "import time; from pathlib import Path; "
        "time.sleep(1); Path('orphan-marker.txt').write_text('orphan')"
    )

    def fail_log(_event: dict) -> None:
        raise RuntimeError("audit unavailable")

    runner = RepoCommandRunner(
        tmp_path,
        20_000,
        30,
        registry=_registry(_python_spec("slow-log", code)),
        event_sink=fail_log,
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        runner.run("slow-log", 10)

    import time
    time.sleep(1.2)
    assert not marker.exists()


def test_mcp_surface_remains_eight_tools_with_batch_command_schema() -> None:
    import inspect
    from types import SimpleNamespace

    from tools.commits import register_commit_tools
    from tools.patches import register_patch_tools
    from tools.reads import register_read_tools
    from tools.tests import register_test_tools

    class FakeMCP:
        def __init__(self) -> None:
            self.tools: dict[str, object] = {}

        def tool(self):
            def register(function):
                self.tools[function.__name__] = function
                return function
            return register

    mcp = FakeMCP()
    context = SimpleNamespace(mcp=mcp)
    register_read_tools(context)
    register_patch_tools(context)
    register_commit_tools(context)
    register_test_tools(context)

    assert set(mcp.tools) == {
        "repo_list_files", "repo_read_file", "repo_search_code",
        "repo_git_status", "repo_git_diff", "repo_apply_patch", "repo_git_commit", "repo_run_test",
    }
    parameters = inspect.signature(mcp.tools["repo_run_test"]).parameters
    assert set(parameters) == {
        "command_key",
        "command_keys",
        "timeout_seconds",
        "stop_on_failure",
        "working_dir",
    }
    commit_parameters = inspect.signature(mcp.tools["repo_git_commit"]).parameters
    assert set(commit_parameters) == {"message", "paths"}