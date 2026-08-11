from __future__ import annotations

import json
import secrets
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from audit.logger import AuditLogger
from gui.config import AppConfig
from gui.log_center import event_details, event_row, filter_events
from gui.log_safety import redact_log_text
from gui.readiness import native_tls_probe_target
from gui.runtime_config import environment_for, merge_environment
from repo.controller import GitController
from repo.git import run_git
from repo.search import _search_with_python, build_ripgrep_command
from security.tokens import http_token_problem, require_strong_http_token
from tools.execution import execute
from tools.test_runner import TEST_COMMANDS

ROOT = Path(__file__).resolve().parents[1]


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        shell=False,
    )


def _controller(path: Path, max_output: int = 100_000) -> GitController:
    return GitController(
        path,
        lambda args, input_text=None, timeout=30: run_git(
            path, args, input_text=input_text, timeout=timeout
        ),
        max_output,
    )


def _context(mode: str, records: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(
        mode=mode,
        audit=None,
        runtime_log=SimpleNamespace(log=lambda **record: records.append(record)),
        server_instance_id="test-instance",
        transport="stdio",
        repo_root=Path("repository").resolve(),
    )


def test_http_token_policy_rejects_placeholders_and_low_variation() -> None:
    assert http_token_problem("CHANGE_ME") is not None
    assert http_token_problem("replace-with-a-long-random-token") is not None
    assert http_token_problem("x" * 64) is not None
    token = secrets.token_urlsafe(32)
    assert http_token_problem(token) is None
    assert require_strong_http_token(token) == token


def test_transport_alias_is_rejected_and_test_mode_requires_audit() -> None:
    with pytest.raises(ValueError, match="stdio or streamable-http"):
        merge_environment(
            AppConfig(),
            {"MCP_TRANSPORT": "http", "HTTP_AUTH_TOKEN": secrets.token_urlsafe(32)},
            override=False,
        )
    config = AppConfig(repo_root=".", mcp_mode="test", audit_log="")
    assert "audit_log_required" in config.validate()
    assert environment_for(AppConfig()).get("AUDIT_REQUIRED") == "false"


def test_native_tls_readiness_uses_public_hostname() -> None:
    config = AppConfig(
        transport="streamable-http",
        http_host="0.0.0.0",
        http_port=8443,
        http_path="/mcp",
        http_public_url="https://mcp.example.test/mcp",
        http_tls_certfile="server.pem",
        http_tls_keyfile="server.key",
    )
    assert native_tls_probe_target(config) == (
        "127.0.0.1",
        8443,
        "mcp.example.test",
        "mcp.example.test",
    )


def test_native_tls_readiness_uses_ipv6_loopback() -> None:
    config = AppConfig(
        transport="streamable-http",
        http_host="::",
        http_port=8443,
        http_public_url="https://mcp.example.test/mcp",
    )
    assert native_tls_probe_target(config)[0] == "::1"


def test_json_secret_values_are_redacted() -> None:
    raw = json.dumps(
        {
            "CONTROL_PLANE_API_KEY": "highly-sensitive-control-plane-key",
            "HTTP_AUTH_TOKEN": "highly-sensitive-http-auth-token",
        }
    )
    redacted = redact_log_text(raw)
    assert "highly-sensitive" not in redacted
    assert redacted.count("<redacted>") == 2


def test_audit_logger_strict_mode_fails_closed(monkeypatch, tmp_path: Path) -> None:
    logger = AuditLogger(str(tmp_path / "audit.jsonl"), strict=True)
    monkeypatch.setattr(
        logger._writer,
        "write",
        lambda _record: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(RuntimeError, match="log write failed"):
        logger.log(event="patch")


def test_execution_distinguishes_permission_policy_environment_and_failure(
    monkeypatch,
) -> None:
    records: list[dict] = []
    monkeypatch.setattr(
        "tools.execution.audit_event",
        lambda _ctx, **record: records.append(record),
    )

    with pytest.raises(PermissionError):
        execute(
            _context("read", records),
            tool="repo_run_test",
            modes=("test",),
            operation=lambda: None,
        )
    assert records[-1]["denial_kind"] == "permission_mode"

    with pytest.raises(PermissionError):
        execute(
            _context("test", records),
            tool="repo_run_test",
            modes=("test",),
            operation=lambda: (_ for _ in ()).throw(
                PermissionError("command is not allowlisted")
            ),
        )
    assert records[-1]["denial_kind"] == "policy"
    assert "allowlisted" in records[-1]["reason"]

    with pytest.raises(FileNotFoundError):
        execute(
            _context("test", records),
            tool="repo_run_test",
            modes=("test",),
            operation=lambda: (_ for _ in ()).throw(
                FileNotFoundError("pytest executable missing")
            ),
        )
    assert records[-1]["status"] == "unavailable"
    assert records[-1]["failure_kind"] == "environment"

    result = execute(
        _context("test", records),
        tool="repo_run_test",
        modes=("test",),
        operation=lambda: {"returncode": 2},
        result_status=lambda value: "success" if value["returncode"] == 0 else "failed",
    )
    assert result["returncode"] == 2
    assert records[-1]["status"] == "failed"
    assert records[-1]["result_code"] == 2


def test_execute_merges_tool_fields_with_command_result_without_duplicate_keys(
    monkeypatch,
) -> None:
    records: list[dict] = []
    monkeypatch.setattr(
        "tools.execution.audit_event",
        lambda _ctx, **record: records.append(record),
    )

    result = execute(
        _context("test", records),
        tool="repo_run_test",
        modes=("test",),
        operation=lambda: {
            "command_key": "go_test",
            "command_kind": "test",
            "command": "go test ./...",
            "status": "failed",
            "success": False,
            "returncode": 1,
            "stdout": "FAIL package",
            "stderr": "",
        },
        command_key="go_test",
        result_status=lambda value: "failed" if not value["success"] else "success",
    )

    assert result["returncode"] == 1
    final = records[-1]
    assert final["command_key"] == "go_test"
    assert final["result_code"] == 1
    assert final["stdout"] == "FAIL package"
    assert final["status"] == "failed"


def test_log_view_explains_policy_denial_and_hides_preflight() -> None:
    events = [
        {"status": "running", "hidden": True, "tool": "repo_run_test"},
        {
            "status": "denied",
            "denial_kind": "policy",
            "reason": "test command is not allowed: gui_smoke",
            "tool": "repo_run_test",
            "source": "mcp",
            "timestamp_iso": "2026-08-04T00:00:00+00:00",
        },
    ]
    visible = filter_events(events, query="", level="ALL")
    assert len(visible) == 1
    assert "策略拒绝" in event_row(visible[0], "zh")
    details = event_details(visible[0], "zh")
    assert "拒绝类型" in details
    assert "policy" in details
    assert "test command is not allowed" in details


def test_ripgrep_command_enforces_size_and_sensitive_globs() -> None:
    command = build_ripgrep_command("needle", 12345)
    assert command[command.index("--max-filesize") + 1] == "12345"
    assert "!.env" in command
    assert "!**/.ssh/**" in command


def test_python_search_enforces_timeout(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("needle\n", encoding="utf-8")
    monkeypatch.setattr("repo.search.time.monotonic", lambda: 100.0)
    with pytest.raises(TimeoutError, match="Python search exceeded"):
        _search_with_python(
            "needle",
            tmp_path,
            limit=10,
            max_output_bytes=1000,
            max_file_bytes=1000,
            timeout_seconds=-1,
        )


def test_patch_result_diff_is_scoped_to_targets(tmp_path: Path) -> None:
    assert _git(tmp_path, "init", "-b", "main").returncode == 0
    assert _git(tmp_path, "config", "user.email", "tests@example.invalid").returncode == 0
    assert _git(tmp_path, "config", "user.name", "Tests").returncode == 0
    (tmp_path / "a.txt").write_text("a0\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b0\n", encoding="utf-8")
    assert _git(tmp_path, "add", "a.txt", "b.txt").returncode == 0
    assert _git(tmp_path, "commit", "-m", "initial").returncode == 0
    (tmp_path / "a.txt").write_text("a1\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b1\n", encoding="utf-8")
    result = _controller(tmp_path).diff_for_paths(["a.txt"])
    assert "a1" in result["diff"]
    assert "b1" not in result["diff"]
    assert len(result["full_hash"]) == 16


def test_release_configuration_is_reproducible_and_safe() -> None:
    assert "gui_smoke" not in TEST_COMMANDS
    gradle = TEST_COMMANDS["gradle_test"][0]
    assert gradle in {"gradlew.bat", "./gradlew"}
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert lock == requirements
    assert all("==" in line for line in lock.splitlines() if line.strip())
    systemd = (ROOT / "systemd/mcp.env.example").read_text(encoding="utf-8")
    assert "HTTP_AUTH_TOKEN=CHANGE_ME" in systemd
    assert "AUDIT_REQUIRED=true" in systemd
    assert not (ROOT / "local_repo_mcp.egg-info").exists()
