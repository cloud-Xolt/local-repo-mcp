"""Backward-compatible entry point for pre-1.3 GUI launchers.

The old implementation mutated widgets after construction, which meant the
same screen had two competing palettes and sizing systems.  Styling now lives
in :mod:`gui.theme` and :mod:`gui.app`; this hook intentionally does nothing.
"""

from __future__ import annotations

from typing import Type

from gui.theme import COLORS

PALETTE = COLORS


def install_ui_overrides(app_class: Type) -> Type:
    return app_class
