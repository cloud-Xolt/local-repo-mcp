from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import commit_all, init_repo
from repo.git import parse_patch_failure_paths
from tools.execution import execute


def test_parse_patch_failure_paths_from_hunk_mismatch() -> None:
    message = (
        "error: patch failed: product/backend/internal/service/schedule.go:162\n"
        "error: product/backend/internal/service/schedule.go: patch does not apply"
    )
    assert parse_patch_failure_paths(message) == [
        "product/backend/internal/service/schedule.go"
    ]


def test_parse_patch_failure_paths_from_missing_file() -> None:
    message = "error: schedule.go: No such file or directory"
    assert parse_patch_failure_paths(message) == ["schedule.go"]


def test_execute_merges_patch_failure_fields(monkeypatch) -> None:
    records: list[dict] = []
    monkeypatch.setattr(
        "tools.execution.audit_event",
        lambda _ctx, **record: records.append(record),
    )
    ctx = SimpleNamespace(mode="write")

    def operation() -> None:
        raise RuntimeError(
            "error: patch failed: product/backend/internal/service/schedule.go:187\n"
            "error: product/backend/internal/service/schedule.go: patch does not apply"
        )

    with pytest.raises(RuntimeError):
        execute(
            ctx,
            tool="repo_apply_patch",
            modes=("write", "test"),
            operation=operation,
            failure_fields=lambda exc: {
                "targets": parse_patch_failure_paths(str(exc)),
            },
        )

    failure = records[-1]
    assert failure["status"] == "failed"
    assert failure["tool"] == "repo_apply_patch"
    assert failure["targets"] == ["product/backend/internal/service/schedule.go"]
    assert "patch does not apply" in failure["reason"]


def test_patch_failure_audit_includes_targets_and_reason(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "app.go").write_text("one\n", encoding="utf-8")
    commit_all(repo)
    (repo / "app.go").write_text("one\ntwo\n", encoding="utf-8")

    records: list[dict] = []
    monkeypatch.setenv("REPO_ROOT", str(repo))
    monkeypatch.setenv("MCP_MODE", "write")
    monkeypatch.setenv("AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("AUDIT_REQUIRED", "true")
    monkeypatch.setattr(
        "tools.execution.audit_event",
        lambda ctx, **record: records.append(record),
    )

    from mcp.server import MCPServer
    from tools.patches import register_patch_tools
    from tools.runtime import build_context

    context = build_context(MCPServer("patch-failure-audit"))
    captured: dict[str, object] = {}

    class CaptureMCP:
        def tool(self):
            def register(function):
                captured["fn"] = function
                return function

            return register

    context.mcp = CaptureMCP()  # type: ignore[assignment]
    register_patch_tools(context)
    tool = captured["fn"]

    patch = (
        "diff --git a/app.go b/app.go\n"
        "--- a/app.go\n"
        "+++ b/app.go\n"
        "@@ -1 +1,2 @@\n"
        " stale\n"
        "+two\n"
    )

    with pytest.raises(RuntimeError, match="patch does not apply"):
        tool(patch)

    failure = records[-1]
    assert failure["status"] == "failed"
    assert failure["tool"] == "repo_apply_patch"
    assert failure["targets"] == ["app.go"]
    assert "patch does not apply" in failure["reason"]
