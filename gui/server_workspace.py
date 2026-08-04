from __future__ import annotations

import json

import customtkinter as ctk

from gui.processes import format_uptime
from gui.theme import COLORS, FONT_SMALL
from gui.tool_visuals import TOOL_VISUALS, build_tool_grid


def _verified(app) -> bool:
    checker = getattr(app, "connection_verified", None)
    return bool(checker()) if callable(checker) else bool(app.last_test)


def build(app) -> None:
    page = app._page()
    running = app.processes.mcp.running
    stdio = app.transport_var.get() == "stdio"
    verified = _verified(app)

    if stdio:
        service_title = app.t("connected") if verified else app.t("stdio_on_demand")
        service_status = app.t("connected") if verified else app.t("on_demand")
        service_hint = (
            app.t("stdio_verified_hint")
            if verified
            else app.t("service_stopped_hint")
        )
    else:
        service_title = (
            app.t("service_running") if running else app.t("service_stopped")
        )
        service_status = app.t("running") if running else app.t("stopped")
        service_hint = (
            app.t("service_running_hint")
            if running
            else app.t("service_stopped_hint")
        )

    _, overview = app._card(
        page, app.t("service_overview"), service_hint, row=0, columnspan=2
    )
    status_line = ctk.CTkFrame(overview, fg_color="transparent")
    status_line.grid(row=0, column=0, sticky="ew")
    status_line.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        status_line,
        text="●",
        text_color=(
            COLORS["success"]
            if verified or running
            else COLORS["subtle"]
        ),
        font=ctk.CTkFont(size=16),
    ).grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(
        status_line,
        text=service_title,
        text_color=COLORS["text"],
        font=ctk.CTkFont(size=22, weight="bold"),
    ).grid(row=0, column=0, sticky="w", padx=(22, 0))

    actions = ctk.CTkFrame(status_line, fg_color="transparent")
    actions.grid(row=0, column=1, sticky="e")
    if stdio or running:
        app._secondary_button(
            actions, app.t("connect"), app._run_smoke_test
        ).pack(side="left", padx=4)
    if not stdio:
        app._primary_button(
            actions,
            app.t("stop_http") if running else app.t("start_http"),
            app._stop_http if running else app._start_http,
            danger=running,
        ).pack(side="left", padx=4)

    metrics = ctk.CTkFrame(overview, fg_color="transparent")
    metrics.grid(row=1, column=0, sticky="ew", pady=(14, 0))
    app._metric(metrics, app.t("status"), service_status, row=0, column=0)
    app._metric(
        metrics,
        app.t("pid"),
        str(app.processes.mcp.pid or "—"),
        row=0,
        column=1,
    )
    app._metric(
        metrics,
        app.t("uptime"),
        format_uptime(app.processes.mcp.uptime),
        row=0,
        column=2,
    )
    app._metric(metrics, app.t("mode"), app.mode_var.get(), row=0, column=3)

    if stdio:
        ctk.CTkLabel(
            overview,
            text=app.t("stdio_process_note"),
            justify="left",
            wraplength=820,
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=FONT_SMALL),
        ).grid(row=2, column=0, sticky="w", pady=(12, 0))

    _, tools_body = app._card(
        page,
        app.t("tool_list"),
        app.t("tool_list_hint"),
        row=1,
        columnspan=2,
    )
    discovered = (
        list(app.last_test.get("tools", []))
        if isinstance(app.last_test, dict)
        else [item.name for item in TOOL_VISUALS]
    )
    build_tool_grid(app, tools_body, discovered)

    _, check_body = app._collapsible(
        page,
        "server_check",
        app.t("connection_details"),
        app.t("connection_details_hint"),
        row=2,
    )
    if check_body is not None:
        text = (
            json.dumps(app.last_test, ensure_ascii=False, indent=2)
            if app.last_test
            else app.t("never")
        )
        box = app._code_box(check_body, text, height=180)
        box.grid(row=0, column=0, columnspan=2, sticky="ew")

    _, client_body = app._collapsible(
        page,
        "server_client",
        app.t("client_config"),
        app.t("client_config_hint"),
        row=3,
    )
    if client_body is not None:
        config_text = app._client_config_text()
        box = app._code_box(client_body, config_text, height=260)
        box.grid(row=0, column=0, columnspan=2, sticky="ew")
        app._secondary_button(
            client_body,
            app.t("copy"),
            lambda: app._copy_text(config_text),
        ).grid(row=1, column=1, sticky="e", pady=(10, 0))
