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
    format_events,
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


def test_list_and_search_audit_fields_are_rendered() -> None:
    list_event = {
        "timestamp": 1,
        "status": "success",
        "tool": "repo_list_files",
        "target": "src",
        "limit": 200,
        "respect_gitignore": True,
        "max_file_bytes": 100_000,
        "include": ["*.go"],
        "exclude": ["vendor/**"],
        "file_count": 12,
        "truncated": False,
        "source": "mcp",
    }
    search_event = {
        "timestamp": 2,
        "status": "success",
        "tool": "repo_search_code",
        "target_hash": "abc123",
        "limit": 50,
        "respect_gitignore": False,
        "match_count": 3,
        "backend": "ripgrep",
        "source": "mcp",
    }

    list_details = event_details(list_event, "zh")
    search_text = format_events([search_event], "zh")

    assert "包含" in list_details
    assert "*.go" in list_details
    assert "12" in list_details
    assert "忽略 .gitignore" in search_text
    assert "ripgrep" in search_text
    assert "3 条匹配" in search_text


def test_failed_patch_row_shows_targets_and_git_reason() -> None:
    event = {
        "timestamp": 1,
        "status": "failed",
        "tool": "repo_apply_patch",
        "targets": ["product/backend/internal/service/schedule.go"],
        "reason": (
            "error: patch failed: product/backend/internal/service/schedule.go:187\n"
            "error: product/backend/internal/service/schedule.go: patch does not apply"
        ),
        "source": "mcp",
    }
    row = event_row(event, "zh")
    assert "schedule.go" in row
    assert "patch failed" in row


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


def test_any_nonzero_process_exit_is_an_error() -> None:
    event = parse_process_lines(
        ["2026-08-04 12:00:00  [MCP exited with code 2]"],
        "mcp",
    )[0]
    assert event["status"] == "failed"
    assert event["level"] == "ERROR"
