from __future__ import annotations

from gui.smoke import main
from tools.test_runner import TEST_COMMANDS


def test_final_gui_composition_smoke() -> None:
    assert TEST_COMMANDS["gui_smoke"][1:] == ["-m", "gui.smoke"]
    main()
