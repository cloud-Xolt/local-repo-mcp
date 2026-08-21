"""Resolve a stable MCP launcher command for source and installed layouts."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_LAUNCHER = SOURCE_ROOT / "launch_mcp.py"


def resolve_runtime_python(python: str | Path | None = None) -> Path:
    """Prefer the project virtualenv when launching MCP child processes."""
    if python is not None:
        return Path(python).expanduser().resolve()
    venv_python = SOURCE_ROOT / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    if venv_python.is_file():
        return venv_python.resolve()
    return Path(sys.executable).resolve()


def launcher_command(
    python: str | Path | None = None,
    *,
    source_launcher: Path | None = None,
) -> list[str]:
    executable = str(resolve_runtime_python(python))
    launcher = SOURCE_LAUNCHER if source_launcher is None else source_launcher
    if launcher.is_file():
        return [executable, str(launcher.resolve())]
    return [executable, "-m", "mcp_app.launcher"]
