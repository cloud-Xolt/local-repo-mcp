from __future__ import annotations

import inspect
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

from gui.processes import ManagedProcess
from gui.app import ASSETS
from gui.desktop import LocalRepoMCPApp
from gui.theme import (
    BTN_HEIGHT,
    CARD_RADIUS,
    COLORS,
    FONT_BODY,
    FONT_SMALL,
    FORM_PRIMARY_WEIGHT,
    FORM_SECONDARY_WEIGHT,
    INPUT_HEIGHT,
    SIDEBAR_WIDTH,
)


def _pid_running(pid: int) -> bool:
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=5,
            check=False,
            shell=False,
        )
        return f'"{pid}"' in result.stdout

    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def test_managed_process_stop_reaps_descendant(tmp_path: Path) -> None:
    pid_file = tmp_path / "descendant.pid"
    parent_code = (
        "import pathlib,subprocess,sys,time;"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
        f"pathlib.Path({str(pid_file)!r}).write_text(str(child.pid));"
        "time.sleep(60)"
    )

    managed = ManagedProcess("cleanup-test")
    managed.start([sys.executable, "-c", parent_code], cwd=tmp_path)
    parent = managed.process
    assert parent is not None

    deadline = time.time() + 5
    while not pid_file.exists() and time.time() < deadline:
        time.sleep(0.05)
    assert pid_file.exists()
    descendant_pid = int(pid_file.read_text(encoding="utf-8"))

    managed.stop(timeout=1)
    assert parent.poll() is not None

    deadline = time.time() + 5
    while _pid_running(descendant_pid) and time.time() < deadline:
        time.sleep(0.05)
    assert not _pid_running(descendant_pid)


def test_gui_uses_one_complete_design_system() -> None:
    assert {
        "bg",
        "surface",
        "sidebar",
        "text",
        "primary",
        "primary_text",
        "accent",
        "danger",
    }.issubset(COLORS)
    assert SIDEBAR_WIDTH == 232
    assert INPUT_HEIGHT == BTN_HEIGHT == 44
    assert CARD_RADIUS >= 12
    assert FONT_BODY >= 15
    assert FONT_SMALL >= 14
    assert (FORM_PRIMARY_WEIGHT, FORM_SECONDARY_WEIGHT) == (3, 2)


def test_desktop_icon_assets_are_packaged() -> None:
    for size in (16, 32, 40, 64, 128, 256):
        data = (ASSETS / f"app-icon-{size}.png").read_bytes()
        assert data.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(data) > 100
        assert struct.unpack(">II", data[16:24]) == (size, size)

    assert (ASSETS / "app-icon.png").read_bytes().startswith(b"\x89PNG")
    assert (ASSETS / "app-icon-source.png").read_bytes().startswith(b"\x89PNG")
    assert (ASSETS / "app-icon.ico").read_bytes().startswith(b"\x00\x00\x01\x00")

    shell_source = inspect.getsource(LocalRepoMCPApp._build_shell)
    assert "image=self._app_icons[40]" in shell_source
    init_source = inspect.getsource(LocalRepoMCPApp.__init__)
    assert "self.iconphoto" in init_source
    assert "self.iconbitmap" in init_source


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    light, dark = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (light + 0.05) / (dark + 0.05)


def test_small_control_text_meets_wcag_aa() -> None:
    assert _contrast("#FFFFFF", COLORS["primary"]) >= 4.5
    assert _contrast(COLORS["text"][0], COLORS["accent_soft"][0]) >= 4.5
    assert _contrast(COLORS["text"][1], COLORS["accent_soft"][1]) >= 4.5


def test_app_does_not_leak_customtkinter_blue_theme() -> None:
    assert "set_default_color_theme" not in inspect.getsource(LocalRepoMCPApp.__init__)
    shell_source = inspect.getsource(LocalRepoMCPApp._build_shell)
    assert 'fg_color=COLORS["surface_alt"]' in shell_source
    assert 'button_color=COLORS["border_strong"]' in shell_source
    assert 'button_hover_color=COLORS["muted"]' in shell_source
