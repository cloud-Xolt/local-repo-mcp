import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui.app import LocalRepoMCPApp


def main() -> None:
    LocalRepoMCPApp().mainloop()


if __name__ == "__main__":
    main()
