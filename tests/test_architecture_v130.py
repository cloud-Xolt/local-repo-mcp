from __future__ import annotations

import secrets
import asyncio
import io
import os
import shlex
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from gui.config import AppConfig
from gui.connection_state import ConnectionState, configuration_fingerprint
from gui.desktop import LocalRepoMCPApp as DesktopApplication
from gui.i18n import tr as translate
from gui.log_workspace import _place_initial_sash
from gui.runtime_config import environment_for
from gui.processes import ManagedProcess
from gui.tool_visuals import TOOL_VISUALS
from gui.tunnel import TunnelManager, command_text
from mcp_app.http_policy import HttpSecurityMiddleware, HttpSecuritySettings
from repo.controller import GitController
from repo.git import run_git
from repo.worktree import initialize_worktree, inspect_worktree, require_worktree_root
from tools.execution import execute


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


def _controller(path: Path) -> GitController:
    return GitController(
        path,
        lambda args, input_text=None, timeout=30: run_git(
            path, args, input_text=input_text, timeout=timeout
        ),
        100_000,
    )


def _init_committed_repo(path: Path) -> None:
    assert _git(path, "init", "-b", "main").returncode == 0
    assert _git(path, "config", "user.email", "tests@example.invalid").returncode == 0
    assert _git(path, "config", "user.name", "Tests").returncode == 0


def test_unborn_repository_has_branch_and_exact_root(tmp_path: Path) -> None:
    info = initialize_worktree(tmp_path)
    assert info.ready
    assert info.is_root
    assert info.branch == "main"
    assert _controller(tmp_path).current_branch() == "main"


def test_child_directory_is_not_an_independent_repository_boundary(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    child = root / "child"
    child.mkdir(parents=True)
    assert _git(root, "init").returncode == 0

    info = inspect_worktree(child)
    assert info.ready
    assert not info.is_root
    assert info.root == root.resolve()
    with pytest.raises(RuntimeError, match="working-tree root"):
        require_worktree_root(child)


def test_runtime_environment_omits_empty_root_and_rejects_weak_token() -> None:
    config = AppConfig()
    assert "REPO_ROOT" not in config.mcp_env()
    environment = environment_for(config)
    assert "REPO_ROOT" not in environment

    weak = AppConfig(
        repo_root=".",
        transport="streamable-http",
        http_auth_token="short",
    )
    with pytest.raises(ValueError, match="at least 32"):
        environment_for(weak)


def test_sensitive_rename_hides_source_and_destination(tmp_path: Path) -> None:
    _init_committed_repo(tmp_path)
    (tmp_path / ".env").write_text("SECRET=value\n", encoding="utf-8")
    assert _git(tmp_path, "add", ".env").returncode == 0
    assert _git(tmp_path, "commit", "-m", "initial").returncode == 0
    assert _git(tmp_path, "mv", ".env", "public.txt").returncode == 0

    controller = _controller(tmp_path)
    status = controller.status_filtered()
    diff = controller.diff_filtered(staged=True)

    assert status["entries"] == []
    assert status["hidden_entries"] == 1
    assert diff["diff"] == ""
    assert diff["hidden_files"] == 1


def test_crlf_worktree_accepts_lf_unified_patch(tmp_path: Path) -> None:
    _init_committed_repo(tmp_path)
    target = tmp_path / "app.txt"
    target.write_bytes(b"one\r\n")
    assert _git(tmp_path, "add", "app.txt").returncode == 0
    assert _git(tmp_path, "commit", "-m", "initial").returncode == 0

    patch = (
        "diff --git a/app.txt b/app.txt\n"
        "--- a/app.txt\n"
        "+++ b/app.txt\n"
        "@@ -1 +1,2 @@\n"
        " one\n"
        "+two\n"
    )
    controller = _controller(tmp_path)
    controller.apply_patch_check(patch)
    controller.apply_patch(patch)
    assert target.read_text(encoding="utf-8").splitlines() == ["one", "two"]


def test_connection_state_drives_reconnect_label() -> None:
    state = ConnectionState()
    fingerprint = configuration_fingerprint(
        repository="repo",
        mode="read",
        transport="stdio",
    )
    state.mark_verified(fingerprint, {"tools": ["repo_git_status"]})
    assert state.matches(fingerprint)

    fake = SimpleNamespace(
        connection_verified=lambda: True,
        t=lambda key: {"connect": "连接", "reconnect": "重新连接"}[key],
    )
    assert DesktopApplication.connection_action_text(fake) == "重新连接"

    state.invalidate()
    assert not state.verified


def test_tool_visual_catalog_has_distinct_theme_tokens() -> None:
    assert len(TOOL_VISUALS) == 7
    assert len({item.name for item in TOOL_VISUALS}) == 7
    assert len({item.color for item in TOOL_VISUALS}) == 7
    assert all(not hasattr(item, "soft_light") for item in TOOL_VISUALS)
    assert all(not hasattr(item, "soft_dark") for item in TOOL_VISUALS)
    assert all(item.icon for item in TOOL_VISUALS)


def test_log_split_defaults_to_larger_detail_pane() -> None:
    calls: list[tuple[int, int, int]] = []

    class Pane:
        def winfo_exists(self):
            return True

        def winfo_width(self):
            return 1000

        def sash_place(self, index, x, y):
            calls.append((index, x, y))

    app = SimpleNamespace(log_paned=Pane())
    _place_initial_sash(app)
    assert calls == [(0, 460, 0)]


def test_tunnel_command_quotes_paths_with_spaces() -> None:
    parts = [
        "C:/Program Files/Python/python.exe",
        "C:/Local Repo MCP/launch_mcp.py",
    ]
    rendered = command_text(parts)
    if os.name == "nt":
        assert rendered == subprocess.list2cmdline(parts)
        assert '"C:/Program Files/Python/python.exe"' in rendered
    else:
        assert shlex.split(rendered) == parts


def test_tunnel_profile_is_updated_structurally(tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        "mcp:\n"
        "  commands:\n"
        "    - channel: main\n"
        "      command: old-python launch_mcp.py\n"
        "other:\n"
        "  command: keep-me\n",
        encoding="utf-8",
    )
    config = AppConfig(
        repo_root=str(tmp_path),
        transport="stdio",
        tunnel_profile_path=str(profile),
    )
    manager = TunnelManager(SimpleNamespace())
    assert manager.repair_profile_command(config) is True
    saved = profile.read_text(encoding="utf-8")
    assert "keep-me" in saved
    assert "old-python launch_mcp.py" not in saved
    assert profile.with_suffix(".yaml.bak").is_file()


def test_nonzero_process_exit_is_logged_as_error() -> None:
    class Process:
        stdout = io.StringIO("output\n")

        @staticmethod
        def wait():
            return 2

    managed = ManagedProcess("MCP")
    managed.process = Process()
    managed._read_output()
    assert any("error: exited with code 2" in line for line in managed.snapshot())


def test_proxy_policy_requires_https_but_accepts_forwarded_end_user() -> None:
    token = secrets.token_urlsafe(32)
    settings = HttpSecuritySettings.build(
        token=token,
        protected_path="/mcp",
        proxy_mode=True,
        trusted_values=["127.0.0.1/32"],
    )
    reached: list[bool] = []
    audit: list[dict] = []

    async def downstream(scope, receive, send):
        reached.append(True)

    async def call(scheme: str):
        messages: list[dict] = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        middleware = HttpSecurityMiddleware(
            downstream,
            settings,
            lambda **record: audit.append(record),
        )
        scope = {
            "type": "http",
            "path": "/mcp",
            "scheme": scheme,
            "client": ("203.0.113.9", 1234),
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "method": "GET",
        }
        await middleware(scope, receive, send)
        return messages

    rejected = asyncio.run(call("http"))
    assert rejected[0]["status"] == 403
    assert audit[-1]["reason"] == "https_required"

    asyncio.run(call("https"))
    assert reached == [True]


def test_http_policy_rejects_weak_token() -> None:
    with pytest.raises(RuntimeError, match="at least 32"):
        HttpSecuritySettings.build(
            token="weak",
            protected_path="/mcp",
            proxy_mode=False,
            trusted_values=[],
        )


def test_permission_denial_is_audited(monkeypatch) -> None:
    records: list[dict] = []
    monkeypatch.setattr(
        "tools.execution.audit_event",
        lambda _ctx, **record: records.append(record),
    )
    ctx = SimpleNamespace(mode="read")
    with pytest.raises(PermissionError):
        execute(
            ctx,
            tool="repo_apply_patch",
            modes=("write", "test"),
            operation=lambda: None,
        )
    assert records[-1]["status"] == "denied"


def test_extended_messages_are_localized() -> None:
    keys = (
        "reconnect",
        "repo_not_git_root",
        "http_token_weak",
        "log_max_bytes_invalid",
        "log_backup_count_invalid",
    )
    for language in ("zh", "en"):
        assert all(translate(language, key) != key for key in keys)
