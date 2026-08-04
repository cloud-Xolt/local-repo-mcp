from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
LOCKFILE = ROOT / "requirements.lock"
MARKER = VENV / ".requirements.sha256"


def _venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _dependency_source() -> Path:
    return LOCKFILE if LOCKFILE.is_file() else REQUIREMENTS


def _requirements_hash() -> str:
    return hashlib.sha256(_dependency_source().read_bytes()).hexdigest()


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    os.replace(temp, path)


def main() -> None:
    if not REQUIREMENTS.is_file():
        raise RuntimeError(f"requirements file not found: {REQUIREMENTS}")
    if not _venv_python().is_file():
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)

    expected = _requirements_hash()
    current = MARKER.read_text(encoding="utf-8").strip() if MARKER.is_file() else ""
    if current != expected:
        subprocess.run(
            [str(_venv_python()), "-m", "pip", "install", "-r", str(_dependency_source())],
            cwd=ROOT,
            check=True,
        )
        _write_atomic(MARKER, expected + "\n")

    print(_venv_python())


if __name__ == "__main__":
    main()
