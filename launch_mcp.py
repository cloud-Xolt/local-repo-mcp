"""Source-checkout wrapper for the packaged MCP launcher."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from mcp_app.launcher import main  # noqa: E402


if __name__ == "__main__":
    try:
        main()
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", None) or str(exc)
        raise SystemExit(
            f"Failed to start MCP server ({missing}). "
            f"interpreter={sys.executable!r}. "
            "Install deps into the project .venv and launch with that interpreter "
            "(keep the .venv/bin/python path; do not follow the symlink to system Python)."
        ) from exc
