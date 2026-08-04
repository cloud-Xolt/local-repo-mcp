from __future__ import annotations

import customtkinter as ctk


def resolve_color(value) -> str:
    """Resolve a CustomTkinter light/dark color for native Tk widgets."""
    if isinstance(value, (tuple, list)):
        index = 1 if ctk.get_appearance_mode().lower() == "dark" else 0
        return str(value[index])
    return str(value)
