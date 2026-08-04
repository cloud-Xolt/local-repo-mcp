from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from gui import log_workspace
from gui.desktop import LocalRepoMCPApp
from gui.log_center import (
    event_details,
    event_row,
    filter_events,
    merge_events,
    parse_jsonl,
    parse_process_lines,
)
from gui.processes import ManagedProcess


def test_application_exposes_advanced_log_page_entry() -> None:
    assert callable(LocalRepoMCPApp._build_logs_center)


def test_log_events_are_sorted_filtered_and_localized() -> None:
    audit = parse_jsonl(
        [
            json.dumps(
                {
                    "timestamp": 20,
                    "status": "denied",
                    "event": "http_authentication",
                    "target": "/mcp",
                }
            )
        ],
        "audit",
    )
    process = parse_process_lines(
        ["2026-08-03 20:00:00  MCP server started"], "mcp"
    )

    events = merge_events(process, audit)
    security = filter_events(events, security_only=True)

    assert events[0]["source"] == "mcp"
    assert len(security) == 1
    assert security[0]["level"] == "SECURITY"
    assert "拒绝" in event_row(security[0], "zh")
    assert "/mcp" in event_details(security[0], "zh")


def test_log_search_matches_targets_and_errors() -> None:
    events = parse_jsonl(
        [
            json.dumps(
                {
                    "timestamp": 1,
                    "status": "failed",
                    "tool": "repo_apply_patch",
                    "targets": ["src/app.py", "tests/test_app.py"],
                    "error_type": "PatchConflict",
                }
            )
        ],
        "mcp",
    )

    assert filter_events(events, query="test_app.py")
    assert filter_events(events, query="PatchConflict", level="ERROR")
    assert not filter_events(events, level="INFO")


def test_log_refresh_cancel_is_idempotent() -> None:
    calls: list[str] = []
    app = SimpleNamespace(
        log_refresh_job="job-1",
        after_cancel=lambda job: calls.append(job),
    )

    log_workspace.cancel(app)
    log_workspace.cancel(app)

    assert calls == ["job-1"]
    assert app.log_refresh_job is None


def test_log_refresh_cancel_tolerates_destroyed_widget() -> None:
    def fail(_job: str) -> None:
        raise RuntimeError("widget destroyed")

    app = SimpleNamespace(log_refresh_job="job-1", after_cancel=fail)

    log_workspace.cancel(app)

    assert app.log_refresh_job is None


def test_managed_process_can_preserve_existing_diagnostics(tmp_path: Path) -> None:
    process = ManagedProcess("Tunnel")
    process.append_log("Doctor passed")

    process.start(
        [sys.executable, "-c", "print('tunnel running')"],
        cwd=tmp_path,
        clear_logs=False,
    )
    process.process.wait(timeout=10)  # type: ignore[union-attr]
    if process._reader is not None:
        process._reader.join(timeout=2)

    snapshot = process.snapshot()
    assert any("Doctor passed" in line for line in snapshot)
    assert any("tunnel running" in line for line in snapshot)


def test_managed_process_clears_logs_by_default(tmp_path: Path) -> None:
    process = ManagedProcess("MCP")
    process.append_log("old diagnostic")

    process.start([sys.executable, "-c", "pass"], cwd=tmp_path)
    process.process.wait(timeout=10)  # type: ignore[union-attr]
    if process._reader is not None:
        process._reader.join(timeout=2)

    assert all("old diagnostic" not in line for line in process.snapshot())
