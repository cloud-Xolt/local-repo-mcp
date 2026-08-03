from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from audit.logger import AuditLogger
from tools.context import audit_event


def test_audit_event_adds_metadata(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    ctx = SimpleNamespace(
        audit=AuditLogger(str(path)),
        server_instance_id="instance",
        transport="stdio",
        mode="read",
        repo_root=tmp_path,
    )
    audit_event(ctx, tool="repo_git_status", status="success")
    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload["event_id"]
    assert payload["server_instance_id"] == "instance"
    assert payload["transport"] == "stdio"
    assert payload["repository_hash"]
    assert payload["process_id"] > 0
