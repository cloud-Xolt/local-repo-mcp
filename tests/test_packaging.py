from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _build_wheel(destination: Path) -> Path:
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    shutil.rmtree(ROOT / "local_repo_mcp.egg-info", ignore_errors=True)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "--isolated", "wheel", ".", "--no-deps",
         "--wheel-dir", str(destination)],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return next(destination.glob("local_repo_mcp-*.whl"))


def test_wheel_contains_only_final_runtime_entry_points(tmp_path: Path) -> None:
    wheel = _build_wheel(tmp_path)
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
            required = {
                "commands/models.py", "commands/registry.py", "commands/runner.py",
                "mcp_app/launcher.py", "mcp_app/service.py", "mcp_app/http_policy.py",
                "tools/runtime.py", "tools/execution.py", "tools/contracts.py", "tools/reads.py",
                "tools/patches.py", "tools/test_runner.py", "tools/tests.py",
                "gui/desktop.py",
                "gui/processes.py", "gui/tunnel.py", "gui/log_workspace.py",
                "gui/colors.py", "gui/readiness.py", "security/tokens.py",
            }
            assert required.issubset(names)
            forbidden = {
                "mcp_app/application.py", "mcp_app/main.py", "mcp_app/server.py",
                "tools/context.py", "tools/context_v2.py", "tools/operation.py",
                "gui/application.py", "gui/runtime_app.py", "gui/process_manager.py",
                "gui/tunnel_manager.py", "gui/ui_overrides.py",
            }
            assert names.isdisjoint(forbidden)
            entry_points = next(
                name for name in names if name.endswith(".dist-info/entry_points.txt")
            )
            metadata_name = next(
                name for name in names if name.endswith(".dist-info/METADATA")
            )
            entry_content = archive.read(entry_points).decode("utf-8")
            metadata_content = archive.read(metadata_name).decode("utf-8")
        assert "local-repo-mcp = mcp_app.launcher:main" in entry_content
        assert "local-repo-mcp-gui = gui.desktop:main" in entry_content
        assert "Version: 1.4.0" in metadata_content
        assert "Requires-Dist: pytest==" in metadata_content
        assert "Requires-Dist: typing-extensions==4.16.0" in metadata_content
    finally:
        shutil.rmtree(ROOT / "build", ignore_errors=True)
        shutil.rmtree(ROOT / "local_repo_mcp.egg-info", ignore_errors=True)


def test_wheel_runs_outside_source_checkout(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheel"
    install_dir = tmp_path / "installed"
    runtime_dir = tmp_path / "runtime"
    wheel_dir.mkdir()
    runtime_dir.mkdir()
    wheel = _build_wheel(wheel_dir)
    try:
        installed = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-deps", "--target",
             str(install_dir), str(wheel)],
            cwd=runtime_dir, text=True, encoding="utf-8", errors="replace",
            capture_output=True, timeout=120, check=False,
        )
        assert installed.returncode == 0, installed.stdout + installed.stderr
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(install_dir)
        smoke = subprocess.run(
            [sys.executable, "-m", "gui.smoke"],
            cwd=runtime_dir, env=environment, text=True, encoding="utf-8",
            errors="replace", capture_output=True, timeout=60, check=False,
        )
        assert smoke.returncode == 0, smoke.stdout + smoke.stderr
        assert "GUI smoke checks passed" in smoke.stdout
    finally:
        shutil.rmtree(ROOT / "build", ignore_errors=True)
        shutil.rmtree(ROOT / "local_repo_mcp.egg-info", ignore_errors=True)
