import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from gui.config import load_config
from mcp_app.server import main


def apply_config_to_environment() -> None:
    config = load_config()
    values = {
        "REPO_ROOT": config.repo_root,
        "MCP_MODE": config.mcp_mode,
        "MAX_FILE_BYTES": str(config.max_file_bytes),
        "MAX_PATCH_BYTES": str(config.max_patch_bytes),
        "MAX_SEARCH_RESULTS": str(config.max_search_results),
        "MAX_OUTPUT_BYTES": str(config.max_output_bytes),
        "ALLOW_DIRTY_WORKTREE": str(config.allow_dirty_worktree).lower(),
        "AUDIT_LOG": config.audit_log,
    }
    for key, value in values.items():
        os.environ[key] = value


if __name__ == "__main__":
    apply_config_to_environment()
    main()
