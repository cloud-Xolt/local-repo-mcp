"""Source-checkout wrapper for the packaged MCP launcher."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from mcp_app.launcher import main  # noqa: E402


if __name__ == "__main__":
    main()
