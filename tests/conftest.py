from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (repo / ".env").write_text("SECRET=1\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/app.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    return repo


@pytest.fixture
def runtime(repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("MCP_MODE", "write")
    monkeypatch.setenv("MAX_FILE_BYTES", "200000")
    monkeypatch.setenv("MAX_PATCH_BYTES", "200000")
    monkeypatch.setenv("MAX_SEARCH_RESULTS", "50")
    monkeypatch.setenv("MAX_OUTPUT_BYTES", "200000")
    monkeypatch.setenv("ALLOW_DIRTY_WORKTREE", "true")
    monkeypatch.setenv("AUDIT_LOG", str(tmp_path / "audit.log"))

    from mcp.server.mcpserver import MCPServer
    from tools.context import build_context

    return build_context(MCPServer("test"))
