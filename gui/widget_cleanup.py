from __future__ import annotations

import customtkinter as ctk
from customtkinter.windows.widgets.scaling.scaling_base_class import CTkScalingBaseClass


def _destroy_option_menu_dropdown(widget: ctk.CTkOptionMenu) -> None:
    menu = getattr(widget, "_dropdown_menu", None)
    if menu is None:
        return
    try:
        CTkScalingBaseClass.destroy(menu)
    except Exception:
        pass
    try:
        if menu.winfo_exists():
            menu.destroy()
    except Exception:
        pass


def _cleanup_ctk_entry(widget: ctk.CTkEntry) -> None:
    callback_name = getattr(widget, "_textvariable_callback_name", "")
    textvariable = getattr(widget, "_textvariable", None)
    if callback_name and textvariable is not None:
        try:
            textvariable.trace_remove("write", callback_name)
        except Exception:
            pass
        widget._textvariable_callback_name = ""
    entry = getattr(widget, "_entry", None)
    if entry is not None:
        try:
            entry.configure(textvariable="")
        except Exception:
            pass


def cleanup_widget_tree(widget) -> None:
    if isinstance(widget, ctk.CTkOptionMenu):
        _destroy_option_menu_dropdown(widget)
    elif isinstance(widget, ctk.CTkEntry):
        _cleanup_ctk_entry(widget)
    for child in widget.winfo_children():
        cleanup_widget_tree(child)


def destroy_children(parent) -> None:
    for child in list(parent.winfo_children()):
        cleanup_widget_tree(child)
        child.destroy()
