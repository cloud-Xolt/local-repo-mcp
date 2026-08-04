"""Configuration-aware Local Repo MCP launcher.

Explicit environment variables take precedence over persisted desktop
configuration. The service module is imported only after configuration is
resolved because it constructs the MCP runtime context at import time.
"""

from __future__ import annotations


def main() -> None:
    from gui.config import load_config
    from gui.runtime_config import apply_to_environment

    apply_to_environment(load_config(), override=False)

    from mcp_app.service import main as run_server

    run_server()


if __name__ == "__main__":
    main()
