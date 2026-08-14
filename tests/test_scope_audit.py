from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp.server import MCPServer

from conftest import commit_all, init_repo
from tools.runtime import build_context
from repo.file_scope import TraversalOptions
from repo.search import search_repository
from tools.execution import execute


@pytest.fixture
def audit_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = init_repo(tmp_path / "repo")
    (root / "keep.txt").write_text("needle keep\n", encoding="utf-8")
    (root / "skip.txt").write_text("needle skip\n", encoding="utf-8")
    (root / ".gitignore").write_text("skip.txt\n", encoding="utf-8")
    commit_all(root)

    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("REPO_ROOT", str(root))
    monkeypatch.setenv("MCP_MODE", "read")
    monkeypatch.setenv("AUDIT_LOG", str(audit_path))
    monkeypatch.setenv("AUDIT_REQUIRED", "true")

    server = MCPServer("scope-audit")
    context = build_context(server)
    return context, audit_path


def test_list_files_audit_includes_scope_fields(audit_context) -> None:
    context, audit_path = audit_context
    options = TraversalOptions(
        path=".",
        limit=200,
        include=("*.txt",),
        exclude=("skip.txt",),
        respect_gitignore=True,
        max_file_bytes=1000,
    )

    execute(
        context,
        tool="repo_list_files",
        modes=("read", "write", "test"),
        operation=lambda: context.filesystem.list_files(options),
        target=".",
        limit=200,
        include=["*.txt"],
        exclude=["skip.txt"],
        respect_gitignore=True,
        max_file_bytes=1000,
    )

    records = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    event = next(
        item
        for item in records
        if item.get("tool") == "repo_list_files" and item.get("status") == "success"
    )
    assert event["include"] == ["*.txt"]
    assert event["exclude"] == ["skip.txt"]
    assert event["respect_gitignore"] is True
    assert event["max_file_bytes"] == 1000
    assert event["file_count"] >= 1
    assert event["truncated"] is False


def test_search_code_audit_includes_scope_and_result_fields(
    audit_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, audit_path = audit_context
    monkeypatch.setattr("repo.search.shutil.which", lambda name: None)

    options = TraversalOptions(
        path=".",
        limit=None,
        respect_gitignore=False,
        max_file_bytes=1000,
    )

    execute(
        context,
        tool="repo_search_code",
        modes=("read", "write", "test"),
        operation=lambda: search_repository(
            "needle",
            context.repo_root,
            options,
            context.max_output_bytes,
            50,
            scope=context.filesystem.scope,
        ),
        target="needle",
        target_is_sensitive=True,
        limit=50,
        respect_gitignore=False,
        max_file_bytes=1000,
    )

    records = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    event = next(
        item
        for item in records
        if item.get("tool") == "repo_search_code" and item.get("status") == "success"
    )
    assert event["respect_gitignore"] is False
    assert event["target_hash"]
    assert event["match_count"] >= 1
    assert event["backend"] == "python"
