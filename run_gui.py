import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
for path in (ROOT, SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from gui.desktop import LocalRepoMCPApp


def main() -> None:
    LocalRepoMCPApp().mainloop()


if __name__ == "__main__":
    main()
