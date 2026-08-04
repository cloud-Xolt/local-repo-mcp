from __future__ import annotations

import os
from tkinter import HORIZONTAL, Listbox, PanedWindow

import customtkinter as ctk

from gui.log_center import (
    event_details,
    event_row,
    filter_events,
    merge_events,
    parse_jsonl,
    parse_process_lines,
    read_tail_lines,
)
from gui.theme import COLORS, CONTROL_RADIUS, FONT_BODY, FONT_SMALL


def _tk_color(value) -> str:
    if isinstance(value, (tuple, list)):
        index = 1 if ctk.get_appearance_mode().lower() == "dark" else 0
        return str(value[index])
    return str(value)


def _place_initial_sash(app) -> None:
    pane = getattr(app, "log_paned", None)
    if pane is None or not pane.winfo_exists():
        return
    width = max(pane.winfo_width(), 900)
    try:
        pane.sash_place(0, int(width * 0.36), 0)
    except Exception:
        pass


def build(app) -> None:
    page = app._page()
    _, body = app._card(
        page,
        app.t("logs"),
        app.t("logs_subtitle"),
        row=0,
        columnspan=2,
    )
    body.grid_columnconfigure(0, weight=1)
    body.grid_rowconfigure(2, weight=1)

    labels = [
        app.t("log_mcp"),
        app.t("log_tunnel"),
        app.t("log_audit"),
        app.t("log_security"),
    ]
    mapping = dict(zip(labels, ("mcp", "tunnel", "audit", "security")))
    reverse = {value: key for key, value in mapping.items()}
    tabs = ctk.CTkSegmentedButton(
        body,
        values=labels,
        height=42,
        selected_color=COLORS["accent_soft"],
        selected_hover_color=COLORS["surface_hover"],
        unselected_color=COLORS["surface_alt"],
        unselected_hover_color=COLORS["surface_hover"],
        text_color=COLORS["text"],
        font=ctk.CTkFont(size=FONT_BODY),
        command=lambda value: change_channel(app, mapping[value]),
    )
    tabs.set(reverse.get(app.log_channel, labels[0]))
    tabs.grid(row=0, column=0, sticky="w")

    filters = ctk.CTkFrame(body, fg_color="transparent")
    filters.grid(row=1, column=0, sticky="ew", pady=(14, 10))
    filters.grid_columnconfigure(0, weight=1)
    search = ctk.CTkEntry(
        filters,
        textvariable=app.log_query_var,
        height=42,
        placeholder_text=app.t("log_search"),
        corner_radius=CONTROL_RADIUS,
        border_width=1,
        border_color=COLORS["border"],
        fg_color=COLORS["surface_alt"],
        text_color=COLORS["text"],
        font=ctk.CTkFont(size=FONT_BODY),
    )
    search.grid(row=0, column=0, sticky="ew", padx=(0, 8))
    search.bind("<KeyRelease>", lambda _event: refresh(app))

    level = ctk.CTkOptionMenu(
        filters,
        variable=app.log_level_var,
        values=["ALL", "INFO", "WARN", "ERROR", "SECURITY"],
        width=120,
        height=42,
        fg_color=COLORS["surface_alt"],
        button_color=COLORS["border_strong"],
        button_hover_color=COLORS["muted"],
        text_color=COLORS["text"],
        command=lambda _value: refresh(app),
    )
    level.grid(row=0, column=1, padx=4)
    ctk.CTkSwitch(
        filters,
        text=app.t("log_live"),
        variable=app.log_auto_var,
        progress_color=COLORS["success"],
        text_color=COLORS["text"],
        command=lambda: toggle(app),
    ).grid(row=0, column=2, padx=8)
    app._secondary_button(
        filters, app.t("refresh"), lambda: refresh(app)
    ).grid(row=0, column=3, padx=(4, 0))

    app.log_paned = PanedWindow(
        body,
        orient=HORIZONTAL,
        sashwidth=8,
        sashrelief="flat",
        showhandle=True,
        handlesize=8,
        background=_tk_color(COLORS["surface"]),
        borderwidth=0,
        relief="flat",
    )
    app.log_paned.grid(row=2, column=0, sticky="nsew")

    list_frame = ctk.CTkFrame(
        app.log_paned,
        fg_color=COLORS["code"],
        corner_radius=10,
        border_width=1,
        border_color=COLORS["border"],
    )
    list_frame.grid_rowconfigure(0, weight=1)
    list_frame.grid_columnconfigure(0, weight=1)
    app.log_listbox = Listbox(
        list_frame,
        height=24,
        activestyle="none",
        background=_tk_color(COLORS["code"]),
        foreground=_tk_color(COLORS["text"]),
        selectbackground=_tk_color(COLORS["accent_soft"]),
        selectforeground=_tk_color(COLORS["text"]),
        borderwidth=0,
        highlightthickness=0,
        font=("Consolas" if os.name == "nt" else "monospace", FONT_SMALL),
    )
    app.log_listbox.grid(row=0, column=0, sticky="nsew", padx=(10, 2), pady=10)
    list_scrollbar = ctk.CTkScrollbar(
        list_frame,
        command=app.log_listbox.yview,
    )
    list_scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 8), pady=10)
    app.log_listbox.configure(yscrollcommand=list_scrollbar.set)
    app.log_listbox.bind("<<ListboxSelect>>", lambda _event: show_selected(app))

    detail_frame = ctk.CTkFrame(
        app.log_paned,
        fg_color=COLORS["surface_alt"],
        corner_radius=10,
        border_width=1,
        border_color=COLORS["border"],
    )
    detail_frame.grid_rowconfigure(1, weight=1)
    detail_frame.grid_columnconfigure(0, weight=1)
    detail_toolbar = ctk.CTkFrame(detail_frame, fg_color="transparent")
    detail_toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
    detail_toolbar.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        detail_toolbar,
        text=app.t("log_details"),
        text_color=COLORS["text"],
        font=ctk.CTkFont(size=FONT_SMALL, weight="bold"),
    ).grid(row=0, column=0, sticky="w")
    view_labels = [app.t("log_readable"), app.t("log_raw")]
    view_mapping = dict(zip(view_labels, ("readable", "raw")))
    view_reverse = {value: key for key, value in view_mapping.items()}
    view = ctk.CTkSegmentedButton(
        detail_toolbar,
        values=view_labels,
        height=34,
        selected_color=COLORS["accent_soft"],
        selected_hover_color=COLORS["surface_hover"],
        unselected_color=COLORS["surface"],
        unselected_hover_color=COLORS["surface_hover"],
        text_color=COLORS["text"],
        font=ctk.CTkFont(size=FONT_SMALL),
        command=lambda value: change_view(app, view_mapping[value]),
    )
    view.set(view_reverse.get(app.log_view_mode, view_labels[0]))
    view.grid(row=0, column=1, sticky="e")

    app.log_detail_box = ctk.CTkTextbox(
        detail_frame,
        height=430,
        corner_radius=8,
        border_width=0,
        fg_color=COLORS["surface_alt"],
        text_color=COLORS["text"],
        font=("Consolas" if os.name == "nt" else "monospace", FONT_SMALL),
        wrap="none",
    )
    app.log_detail_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 0))
    detail_xscroll = ctk.CTkScrollbar(
        detail_frame,
        orientation="horizontal",
        command=app.log_detail_box.xview,
    )
    detail_xscroll.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 6))
    app.log_detail_box.configure(
        state="disabled",
        xscrollcommand=detail_xscroll.set,
    )

    copy_bar = ctk.CTkFrame(detail_frame, fg_color="transparent")
    copy_bar.grid(row=3, column=0, sticky="e", padx=10, pady=(0, 10))
    app._secondary_button(
        copy_bar, app.t("copy_summary"), lambda: copy_selected(app, raw=False)
    ).pack(side="left", padx=4)
    app._secondary_button(
        copy_bar, app.t("copy_raw"), lambda: copy_selected(app, raw=True)
    ).pack(side="left", padx=(4, 0))

    app.log_paned.add(list_frame, minsize=280, width=400, stretch="always")
    app.log_paned.add(detail_frame, minsize=480, width=700, stretch="always")
    app.after_idle(lambda: _place_initial_sash(app))
    refresh(app)
    schedule(app)


def load_events(app) -> list[dict]:
    if app.log_channel == "mcp":
        return merge_events(
            parse_jsonl(read_tail_lines(app.mcp_log_var.get()), "mcp"),
            parse_process_lines(app.processes.mcp.snapshot(), "mcp"),
        )
    if app.log_channel == "tunnel":
        return parse_process_lines(app.processes.tunnel.snapshot(), "tunnel")
    return parse_jsonl(read_tail_lines(app.audit_var.get()), "audit")


def refresh(app) -> None:
    if app.current_page != "logs" or not hasattr(app, "log_listbox"):
        return
    previous = selected_index(app)
    app.log_events = filter_events(
        load_events(app),
        query=app.log_query_var.get(),
        level=app.log_level_var.get(),
        security_only=app.log_channel == "security",
        limit=500,
    )
    app.log_listbox.delete(0, "end")
    for event in app.log_events:
        app.log_listbox.insert("end", event_row(event, app.config_data.language))
    if app.log_events:
        index = min(previous if previous is not None else 0, len(app.log_events) - 1)
        app.log_listbox.selection_set(index)
        app.log_listbox.activate(index)
    show_selected(app)


def selected_index(app) -> int | None:
    if not hasattr(app, "log_listbox"):
        return None
    selected = app.log_listbox.curselection()
    return int(selected[0]) if selected else None


def show_selected(app) -> None:
    index = selected_index(app)
    if index is None or index >= len(app.log_events):
        text = app.t("empty_log")
    else:
        text = event_details(
            app.log_events[index],
            app.config_data.language,
            raw=app.log_view_mode == "raw",
        )
    app.log_detail_box.configure(state="normal")
    app.log_detail_box.delete("1.0", "end")
    app.log_detail_box.insert("1.0", text)
    app.log_detail_box.xview_moveto(0)
    app.log_detail_box.yview_moveto(0)
    app.log_detail_box.configure(state="disabled")


def copy_selected(app, *, raw: bool) -> None:
    index = selected_index(app)
    if index is None or index >= len(app.log_events):
        return
    app._copy_text(
        event_details(
            app.log_events[index],
            app.config_data.language,
            raw=raw,
        )
    )


def change_channel(app, channel: str) -> None:
    app.log_channel = channel
    refresh(app)


def change_view(app, mode: str) -> None:
    app.log_view_mode = mode
    show_selected(app)


def toggle(app) -> None:
    if not app.log_auto_var.get() and app.log_refresh_job is not None:
        try:
            app.after_cancel(app.log_refresh_job)
        except Exception:
            pass
        app.log_refresh_job = None
    schedule(app)


def schedule(app) -> None:
    if app.current_page != "logs" or not app.log_auto_var.get():
        return
    if app.log_refresh_job is not None:
        return

    def tick() -> None:
        app.log_refresh_job = None
        if app.current_page != "logs":
            return
        refresh(app)
        schedule(app)

    app.log_refresh_job = app.after(3000, tick)


def cancel(app) -> None:
    job = getattr(app, "log_refresh_job", None)
    if job is None:
        return
    try:
        app.after_cancel(job)
    except Exception:
        pass
    finally:
        app.log_refresh_job = None
