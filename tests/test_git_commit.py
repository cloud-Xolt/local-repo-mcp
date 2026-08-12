from __future__ import annotations

from pathlib import Path

import pytest

from conftest import commit_all, init_repo
from gui.config import AppConfig
from repo.controller import GitController
from repo.git import run_git
from tools.commits import register_commit_tools


def _git_controller(repo: Path) -> GitController:
    def runner(args, input_text=None, timeout=30):
        return run_git(repo, args, input_text=input_text, timeout=timeout)

    return GitController(repo, runner, max_output_bytes=20_000)


def _capture_commit_tool(context):
    captured: dict[str, object] = {}

    class CaptureMCP:
        def tool(self):
            def register(function):
                captured["fn"] = function
                return function

            return register

    context.mcp = CaptureMCP()
    register_commit_tools(context)
    return captured["fn"]


def test_appconfig_exports_allow_git_commit_env(tmp_path: Path) -> None:
    enabled = AppConfig(repo_root=str(tmp_path), allow_git_commit=True).mcp_env()
    disabled = AppConfig(repo_root=str(tmp_path), allow_git_commit=False).mcp_env()
    assert enabled["ALLOW_GIT_COMMIT"] == "true"
    assert disabled["ALLOW_GIT_COMMIT"] == "false"


def test_commit_paths_skips_sensitive_files(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")
    commit_all(repo)
    (repo / "src" / "app.py").write_text("print(2)\n", encoding="utf-8")
    (repo / ".env").write_text("SECRET=1\n", encoding="utf-8")

    result = _git_controller(repo).commit_paths("safe change")
    assert result["committed"] is True
    assert result["paths"] == ["src/app.py"]
    assert result["hidden_paths"] == 1
    assert (repo / ".env").read_text(encoding="utf-8") == "SECRET=1\n"
    status = run_git(repo, ["status", "--porcelain"]).stdout
    assert ".env" in status


def test_commit_paths_rejects_explicit_sensitive_path(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "readme.txt").write_text("ok\n", encoding="utf-8")
    commit_all(repo)
    (repo / ".env").write_text("SECRET=1\n", encoding="utf-8")

    with pytest.raises(PermissionError, match="not allowed"):
        _git_controller(repo).commit_paths("leak", paths=[".env"])


def test_repo_git_commit_requires_enablement(tmp_path: Path, monkeypatch) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    commit_all(repo)
    (repo / "a.txt").write_text("b\n", encoding="utf-8")
    audit = tmp_path / "audit.jsonl"
    audit.write_text("", encoding="utf-8")

    monkeypatch.setenv("REPO_ROOT", str(repo))
    monkeypatch.setenv("MCP_MODE", "write")
    monkeypatch.setenv("ALLOW_GIT_COMMIT", "false")
    monkeypatch.setenv("AUDIT_LOG", str(audit))
    monkeypatch.setenv("AUDIT_REQUIRED", "true")

    from mcp.server import MCPServer
    from tools.runtime import build_context

    context = build_context(MCPServer("commit-disabled"))
    tool = _capture_commit_tool(context)
    with pytest.raises(PermissionError, match="disabled"):
        tool("should fail")


def test_repo_git_commit_succeeds_when_enabled(tmp_path: Path, monkeypatch) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    commit_all(repo)
    (repo / "a.txt").write_text("b\n", encoding="utf-8")
    audit = tmp_path / "audit.jsonl"
    audit.write_text("", encoding="utf-8")

    monkeypatch.setenv("REPO_ROOT", str(repo))
    monkeypatch.setenv("MCP_MODE", "write")
    monkeypatch.setenv("ALLOW_GIT_COMMIT", "true")
    monkeypatch.setenv("AUDIT_LOG", str(audit))
    monkeypatch.setenv("AUDIT_REQUIRED", "true")

    from mcp.server import MCPServer
    from tools.runtime import build_context

    context = build_context(MCPServer("commit-enabled"))
    assert context.allow_git_commit is True
    tool = _capture_commit_tool(context)
    result = tool("enabled commit", ["a.txt"])
    assert result["committed"] is True
    assert result["paths"] == ["a.txt"]
    assert len(result["commit"]) >= 7
