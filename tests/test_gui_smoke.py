from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from gui.smoke import main
from tools.test_runner import TEST_COMMANDS

ROOT = Path(__file__).resolve().parents[1]


def test_final_gui_composition_smoke() -> None:
    assert TEST_COMMANDS["gui_smoke"][1:] == ["run_gui.py", "--smoke"]
    main()


def test_source_gui_smoke_entry_runs_in_clean_process() -> None:
    result = subprocess.run(
        [sys.executable, "run_gui.py", "--smoke"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "GUI smoke checks passed" in result.stdout
