import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from mcp_app.service import main, mcp  # noqa: E402,F401

if __name__ == "__main__":
    main()
