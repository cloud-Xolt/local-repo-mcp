"""Resolve a stable MCP launcher command for source and installed layouts."""

from __future__ import annotations

import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_LAUNCHER = SOURCE_ROOT / "launch_mcp.py"


def launcher_command(
    python: str | Path | None = None,
    *,
    source_launcher: Path | None = None,
) -> list[str]:
    executable = str(Path(python or sys.executable).resolve())
    launcher = SOURCE_LAUNCHER if source_launcher is None else source_launcher
    if launcher.is_file():
        return [executable, str(launcher.resolve())]
    return [executable, "-m", "mcp_app.launcher"]
