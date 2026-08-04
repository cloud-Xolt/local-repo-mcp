from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wheel_contains_only_final_runtime_entry_points(tmp_path: Path) -> None:
    shutil.rmtree(ROOT / 'build', ignore_errors=True)
    shutil.rmtree(ROOT / 'local_repo_mcp.egg-info', ignore_errors=True)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "--isolated", "wheel", ".", "--no-deps",
         "--wheel-dir", str(tmp_path)],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheel = next(tmp_path.glob("local_repo_mcp-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        required = {
            "mcp_app/launcher.py", "mcp_app/service.py", "mcp_app/http_policy.py",
            "tools/runtime.py", "tools/execution.py", "tools/reads.py",
            "tools/patches.py", "tools/tests.py", "gui/desktop.py",
            "gui/processes.py", "gui/tunnel.py", "gui/log_workspace.py",
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
        content = archive.read(entry_points).decode("utf-8")
    assert "local-repo-mcp = mcp_app.launcher:main" in content
    assert "local-repo-mcp-gui = gui.desktop:main" in content
