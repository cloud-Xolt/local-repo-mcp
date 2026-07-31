"""Stable launcher used by the GUI and Secure MCP Tunnel."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from gui.config import apply_config_to_environment, load_config  # noqa: E402


def main() -> None:
    # RuntimeContext is created when mcp_app.server is imported, therefore the
    # persisted GUI configuration must be applied before importing the server.
    apply_config_to_environment(load_config())
    from mcp_app.server import main as run_server  # noqa: E402

    run_server()


if __name__ == "__main__":
    main()
