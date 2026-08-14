from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from audit.logger import AuditLogger
from gui.config import AppConfig
from gui.log_center import event_time, format_jsonl, read_tail_lines
from gui.processes import ManagedProcess


def test_tail_reader_is_bounded_and_returns_latest_lines(tmp_path: Path) -> None:
    path = tmp_path / "runtime.jsonl"
    path.write_text(
        "".join(json.dumps({"index": index}) + "\n" for index in range(1000)),
        encoding="utf-8",
    )

    lines = read_tail_lines(str(path), max_lines=10, max_bytes=100_000)

    assert len(lines) == 10
    assert json.loads(lines[0])["index"] == 990
    assert json.loads(lines[-1])["index"] == 999


def test_event_time_converts_utc_iso_to_local_time() -> None:
    iso = "2026-08-13T11:32:00.456+00:00"
    event = {"timestamp_iso": iso, "timestamp": 0}
    expected = (
        datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    )
    assert event_time(event) == expected


def test_readable_formatter_localizes_and_shows_target() -> None:
    line = json.dumps(
        {
            "timestamp": 1785731200,
            "status": "success",
            "tool": "repo_read_file",
            "target": "src/app.py",
            "transport": "stdio",
            "mode": "read",
            "repository": "demo",
            "process_id": 42,
        }
    )

    readable = format_jsonl([line], "zh")
    raw = format_jsonl([line], "zh", raw=True)

    assert "成功" in readable
    assert "读取文件" in readable
    assert "src/app.py" in readable
    assert "STDIO" in readable
    assert raw == line


def test_malformed_jsonl_remains_visible() -> None:
    rendered = format_jsonl(["not-json"], "en")

    assert "Failed" in rendered
    assert "not-json" in rendered


def test_runtime_log_path_is_propagated_to_mcp_environment(tmp_path: Path) -> None:
    config = AppConfig(mcp_log=str(tmp_path / "mcp.jsonl"))

    assert config.mcp_env()["MCP_LOG"] == str(tmp_path / "mcp.jsonl")


def test_jsonl_logger_keeps_concurrent_records_parseable(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(str(path))

    def write_batch(worker: int) -> None:
        for item in range(40):
            logger.log(worker=worker, item=item, status="success")

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(write_batch, range(8)))

    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 320
    assert all(record["status"] == "success" for record in records)


def test_process_log_lines_include_local_timestamp() -> None:
    process = ManagedProcess("MCP")

    process.append_log("connection started")

    line = process.snapshot()[0]
    assert line.endswith("connection started")
    assert len(line.split("  ", 1)[0]) == 19


def test_gui_and_server_use_shared_runtime_log() -> None:
    root = Path(__file__).resolve().parents[1]
    desktop = (root / "gui/desktop.py").read_text(encoding="utf-8")
    workspace = (root / "gui/log_workspace.py").read_text(encoding="utf-8")
    service = (root / "src/mcp_app/service.py").read_text(encoding="utf-8")
    runtime = (root / "src/tools/runtime.py").read_text(encoding="utf-8")

    assert "read_tail_lines(app.mcp_log_var.get())" in workspace
    assert "log_callback=self.processes.mcp.append_log" in desktop
    assert 'event="server_stop", status=stop_status' in service
    assert 'os.environ.get("MCP_LOG"' in runtime


def test_process_logs_redact_common_credentials() -> None:
    process = ManagedProcess("Tunnel")

    process.append_log("Authorization: Bearer abcdefghijklmnopqrstuvwxyz")
    process.append_log("CONTROL_PLANE_API_KEY=runtime-secret-value")
    process.append_log("OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456")
    process.append_log("https://example.test/mcp?token=query-secret")

    output = "\n".join(process.snapshot())
    assert "abcdefghijklmnopqrstuvwxyz" not in output
    assert "runtime-secret-value" not in output
    assert "query-secret" not in output
    assert "<redacted>" in output


def test_jsonl_logger_rotates_and_keeps_records_parseable(tmp_path: Path) -> None:
    path = tmp_path / "runtime.jsonl"
    logger = AuditLogger(str(path), max_bytes=64_000, backup_count=2)

    for index in range(500):
        logger.log(
            status="success",
            event="rotation_test",
            index=index,
            payload="x" * 256,
        )

    files = [path, path.with_name(path.name + ".1")]
    assert all(item.is_file() for item in files)
    assert not path.with_name(path.name + ".3").exists()
    for item in files:
        records = [
            json.loads(line)
            for line in item.read_text(encoding="utf-8").splitlines()
        ]
        assert records
        assert all(record["schema_version"] == 1 for record in records)
