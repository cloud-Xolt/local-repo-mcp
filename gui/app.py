from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from pathlib import Path
from tkinter import Label, PhotoImage, TclError, filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from gui import log_workspace, server_workspace
from gui.colors import resolve_color
from gui.config import AppConfig, load_config, save_config
from gui.connection import run_connection_test as run_smoke_test
from gui.dialogs import show_result_dialog
from gui.i18n import tr
from gui.widget_cleanup import destroy_children
from gui.processes import ProcessManager, format_uptime
from mcp_app.runtime import launcher_command
from mcp_app.version import VERSION
from repo.worktree import inspect_worktree
from gui.theme import (
    BTN_HEIGHT,
    CARD_RADIUS,
    COLORS,
    CONTENT_PADX,
    CONTROL_RADIUS,
    FONT_BODY,
    FONT_CAPTION,
    FONT_PAGE,
    FONT_SECTION,
    FONT_SMALL,
    FORM_PRIMARY_WEIGHT,
    FORM_SECONDARY_WEIGHT,
    INPUT_HEIGHT,
    SIDEBAR_WIDTH,
)
from gui.tunnel import TunnelManager

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "gui" / "assets"
GITHUB_URL = "https://github.com/cloud-Xolt/local-repo-mcp"

PAGE_SUBTITLES = {
    "home": "home_subtitle",
    "server": "server_subtitle",
    "chatgpt": "chatgpt_subtitle",
    "logs": "logs_subtitle",
    "about": "about_subtitle",
}

NAV_ICONS = {
    "home": "⌂",
    "server": "◉",
    "chatgpt": "✦",
    "logs": "≡",
    "about": "?",
}


class LocalRepoMCPApp(ctk.CTk):
    def __init__(self) -> None:
        self.config_data = load_config()
        ctk.set_appearance_mode(self.config_data.appearance)
        super().__init__()

        self.title("Local Repo MCP")
        self._app_icons: dict[int, PhotoImage] = {}
        for size in (16, 32, 40, 64):
            try:
                self._app_icons[size] = PhotoImage(
                    file=str(ASSETS / f"app-icon-{size}.png")
                )
            except TclError:
                pass
        self.iconphoto(
            True,
            *(
                self._app_icons[size]
                for size in (16, 32, 64)
                if size in self._app_icons
            ),
        )
        try:
            self.iconbitmap(default=str(ASSETS / "app-icon.ico"))
        except TclError:
            # iconphoto above remains the portable fallback on non-Windows Tk.
            pass
        self.geometry("1280x820")
        self.minsize(1060, 700)
        self.configure(fg_color=COLORS["bg"])

        self.processes = ProcessManager()
        self.tunnel = TunnelManager(self.processes)
        self.current_page = "home"
        self.busy = False
        self._busy_buttons: list = []
        self.last_test: dict | None = None
        self.api_key_visible = False
        self.token_visible = False
        self._api_key_entry = None
        self._api_key_toggle_btn = None
        self._tunnel_watch_job: str | None = None
        self._tunnel_seen_running = False
        self.section_state = {
            "home_http": True,
            "home_advanced": False,
            "server_check": False,
            "server_client": False,
            "chatgpt_auth": False,
            "chatgpt_advanced": False,
            "about_security": False,
        }
        self.log_channel = "mcp"
        self.log_view_mode = "readable"
        self.log_events: list[dict] = []
        self.log_refresh_job: str | None = None

        self._init_variables()
        self._build_shell()
        self._show_page("home")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def t(self, key: str) -> str:
        return tr(self.config_data.language, key)

    def _init_variables(self) -> None:
        cfg = self.config_data
        self.repo_var = ctk.StringVar(value=cfg.repo_root)
        self.mode_var = ctk.StringVar(value=cfg.mcp_mode)
        self.transport_var = ctk.StringVar(value=cfg.transport)
        self.http_host_var = ctk.StringVar(value=cfg.http_host)
        self.http_port_var = ctk.StringVar(value=str(cfg.http_port))
        self.http_path_var = ctk.StringVar(value=cfg.http_path)
        self.http_token_var = ctk.StringVar(value=cfg.http_auth_token)
        self.allowed_hosts_var = ctk.StringVar(value=cfg.http_allowed_hosts)
        self.allowed_origins_var = ctk.StringVar(value=cfg.http_allowed_origins)
        self.http_public_url_var = ctk.StringVar(value=cfg.http_public_url)
        self.http_tls_cert_var = ctk.StringVar(value=cfg.http_tls_certfile)
        self.http_tls_key_var = ctk.StringVar(value=cfg.http_tls_keyfile)
        self.http_tls_ca_var = ctk.StringVar(value=cfg.http_tls_client_ca)
        self.http_client_cert_var = ctk.StringVar(value=cfg.http_client_certfile)
        self.http_client_key_var = ctk.StringVar(value=cfg.http_client_keyfile)
        self.http_tls_proxy_var = ctk.BooleanVar(value=cfg.http_tls_terminated_proxy)
        self.http_proxy_ips_var = ctk.StringVar(value=cfg.http_proxy_trusted_ips)
        self.http_request_kb_var = ctk.StringVar(value=str(cfg.http_max_request_bytes // 1000))
        self.http_json_var = ctk.BooleanVar(value=cfg.http_json_response)
        self.http_stateless_var = ctk.BooleanVar(value=cfg.http_stateless)
        self.max_file_var = ctk.StringVar(value=str(cfg.max_file_bytes // 1000))
        self.max_patch_var = ctk.StringVar(value=str(cfg.max_patch_bytes // 1000))
        self.max_search_var = ctk.StringVar(value=str(cfg.max_search_results))
        self.max_output_var = ctk.StringVar(value=str(cfg.max_output_bytes // 1000))
        self.test_timeout_var = ctk.StringVar(value=str(cfg.test_timeout_max))
        self.test_artifact_dir_var = ctk.StringVar(value=cfg.test_artifact_dir)
        self.test_max_images_var = ctk.StringVar(value=str(cfg.max_test_images))
        self.test_image_max_kb_var = ctk.StringVar(value=str(cfg.max_test_image_bytes // 1024))
        self.test_image_total_kb_var = ctk.StringVar(value=str(cfg.max_test_image_total_bytes // 1024))
        self.read_image_max_kb_var = ctk.StringVar(value=str(cfg.max_read_image_bytes // 1024))
        self.audit_var = ctk.StringVar(value=cfg.audit_log)
        self.mcp_log_var = ctk.StringVar(value=cfg.mcp_log)
        self.log_max_kb_var = ctk.StringVar(value=str(cfg.log_max_bytes // 1000))
        self.log_backup_var = ctk.StringVar(value=str(cfg.log_backup_count))
        self.dirty_var = ctk.BooleanVar(value=cfg.allow_dirty_worktree)
        self.git_commit_var = ctk.BooleanVar(value=cfg.allow_git_commit)
        self.tunnel_path_var = ctk.StringVar(value=cfg.tunnel_client_path)
        self.tunnel_id_var = ctk.StringVar(value=cfg.tunnel_id)
        self.tunnel_profile_var = ctk.StringVar(value=cfg.tunnel_profile)
        self.tunnel_profile_path_var = ctk.StringVar(value=cfg.tunnel_profile_path)
        self.tunnel_http_proxy_var = ctk.StringVar(value=cfg.tunnel_http_proxy)
        self.api_key_var = ctk.StringVar(value=cfg.control_plane_api_key)
        self.log_query_var = ctk.StringVar(value="")
        self.log_level_var = ctk.StringVar(value="ALL")
        self.log_auto_var = ctk.BooleanVar(value=True)

    def _build_shell(self) -> None:
        self._api_key_entry = None
        self._api_key_toggle_btn = None
        destroy_children(self)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(
            self,
            width=SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=COLORS["sidebar"],
            border_width=0,
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=16, pady=(22, 24))
        if 40 in self._app_icons:
            Label(
                brand,
                image=self._app_icons[40],
                width=40,
                height=40,
                background=resolve_color(COLORS["sidebar"]),
                borderwidth=0,
                highlightthickness=0,
            ).pack(side="left")
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left", padx=(11, 0))
        ctk.CTkLabel(
            brand_text,
            text="Local Repo MCP",
            anchor="w",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand_text,
            text=f"v{VERSION}",
            anchor="w",
            font=ctk.CTkFont(size=FONT_CAPTION),
            text_color=COLORS["muted"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            sidebar,
            text=self.t("navigation").upper(),
            anchor="w",
            font=ctk.CTkFont(size=FONT_CAPTION, weight="bold"),
            text_color=COLORS["subtle"],
        ).pack(fill="x", padx=18, pady=(0, 8))

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for key in ("home", "server", "chatgpt", "logs", "about"):
            button = ctk.CTkButton(
                sidebar,
                text=f"{NAV_ICONS[key]}    {self.t(key)}",
                anchor="w",
                height=44,
                corner_radius=CONTROL_RADIUS,
                border_width=0,
                fg_color="transparent",
                hover_color=COLORS["sidebar_hover"],
                text_color=COLORS["text"],
                font=ctk.CTkFont(size=FONT_BODY),
                command=lambda page=key: self._show_page(page),
            )
            button.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = button

        ctk.CTkFrame(sidebar, fg_color="transparent").pack(fill="both", expand=True)

        repo_summary = ctk.CTkFrame(
            sidebar,
            fg_color=COLORS["surface"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )
        repo_summary.pack(fill="x", padx=10, pady=(0, 12))
        ctk.CTkLabel(
            repo_summary,
            text=self._repo_name(),
            anchor="w",
            font=ctk.CTkFont(size=FONT_SMALL, weight="bold"),
            text_color=COLORS["text"],
        ).pack(fill="x", padx=12, pady=(11, 2))
        ctk.CTkLabel(
            repo_summary,
            text=f"{self._git_branch()}  ·  {self.mode_var.get().upper()}",
            anchor="w",
            font=ctk.CTkFont(size=FONT_SMALL),
            text_color=COLORS["muted"],
        ).pack(fill="x", padx=12, pady=(0, 11))

        prefs = ctk.CTkFrame(sidebar, fg_color="transparent")
        prefs.pack(fill="x", padx=10, pady=(0, 16))

        language = ctk.CTkOptionMenu(
            prefs,
            values=["中文", "English"],
            height=INPUT_HEIGHT,
            corner_radius=CONTROL_RADIUS,
            fg_color=COLORS["surface_alt"],
            button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["border_strong"],
            dropdown_fg_color=COLORS["surface"],
            dropdown_hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=FONT_SMALL),
            command=self._change_language,
        )
        language.set("中文" if self.config_data.language == "zh" else "English")
        language.pack(side="left", fill="x", expand=True, padx=(0, 4))

        appearance = ctk.CTkOptionMenu(
            prefs,
            values=[self.t("system"), self.t("light"), self.t("dark")],
            height=INPUT_HEIGHT,
            corner_radius=CONTROL_RADIUS,
            fg_color=COLORS["surface_alt"],
            button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["border_strong"],
            dropdown_fg_color=COLORS["surface"],
            dropdown_hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=FONT_SMALL),
            command=self._change_appearance,
        )
        appearance.set(
            {
                "system": self.t("system"),
                "light": self.t("light"),
                "dark": self.t("dark"),
            }[self.config_data.appearance]
        )
        appearance.pack(side="left", fill="x", expand=True, padx=(4, 0))

        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.content, fg_color="transparent", height=88)
        header.grid(row=0, column=0, sticky="ew", padx=CONTENT_PADX, pady=(22, 4))
        header.grid_columnconfigure(0, weight=1)

        title_wrap = ctk.CTkFrame(header, fg_color="transparent")
        title_wrap.grid(row=0, column=0, sticky="w")
        self.page_title = ctk.CTkLabel(
            title_wrap,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=FONT_PAGE, weight="bold"),
            text_color=COLORS["text"],
        )
        self.page_title.pack(anchor="w")
        self.page_subtitle = ctk.CTkLabel(
            title_wrap,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=FONT_BODY),
            text_color=COLORS["muted"],
        )
        self.page_subtitle.pack(anchor="w", pady=(3, 0))

        self.banner = ctk.CTkLabel(
            header,
            text=self.t("ready"),
            height=30,
            corner_radius=15,
            fg_color=COLORS["surface_alt"],
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=FONT_SMALL, weight="bold"),
        )
        self.banner.grid(row=0, column=1, sticky="e", padx=(16, 0))

        self.page_container = ctk.CTkFrame(self.content, fg_color="transparent")
        self.page_container.grid(
            row=1,
            column=0,
            padx=CONTENT_PADX,
            pady=(10, 28),
            sticky="nsew",
        )
        self.page_container.grid_columnconfigure(0, weight=1)
        self.page_container.grid_rowconfigure(0, weight=1)

    def _show_page(self, page: str) -> None:
        log_workspace.cancel(self)
        self._cancel_tunnel_watch()
        self._api_key_entry = None
        self._api_key_toggle_btn = None
        self._busy_buttons = []
        self.current_page = page
        for key, button in self.nav_buttons.items():
            active = key == page
            button.configure(
                fg_color=COLORS["sidebar_active"] if active else "transparent",
                text_color=COLORS["text"],
                font=ctk.CTkFont(size=FONT_BODY, weight="bold" if active else "normal"),
            )
        self.page_title.configure(text=self.t(page))
        self.page_subtitle.configure(text=self.t(PAGE_SUBTITLES[page]))

        destroy_children(self.page_container)

        {
            "home": self._build_home,
            "server": self._build_server,
            "chatgpt": self._build_chatgpt,
            "logs": self._build_logs_center,
            "about": self._build_about,
        }[page]()
        if page == "chatgpt":
            self._tunnel_seen_running = self.processes.tunnel.running
            self._schedule_tunnel_watch()

    def _cancel_tunnel_watch(self) -> None:
        job = self._tunnel_watch_job
        if job is None:
            return
        try:
            self.after_cancel(job)
        except Exception:
            pass
        finally:
            self._tunnel_watch_job = None

    def _schedule_tunnel_watch(self) -> None:
        if self.current_page != "chatgpt" or self._tunnel_watch_job is not None:
            return
        self._tunnel_watch_job = self.after(2000, self._on_tunnel_watch_tick)

    def _on_tunnel_watch_tick(self) -> None:
        self._tunnel_watch_job = None
        if self.current_page != "chatgpt":
            return
        running = self.processes.tunnel.running
        if self._tunnel_seen_running and not running:
            code = self.processes.tunnel.last_exit_code
            detail = f" (exit {code})" if code is not None else ""
            self._status(self.t("tunnel_exited_unexpectedly") + detail, "danger")
            self._show_page("chatgpt")
            return
        self._tunnel_seen_running = running
        self._schedule_tunnel_watch()

    def _page(self):
        frame = ctk.CTkScrollableFrame(
            self.page_container,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COLORS["border_strong"],
            scrollbar_button_hover_color=COLORS["muted"],
        )
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        return frame

    def _card(
        self,
        parent,
        title: str,
        subtitle: str = "",
        *,
        row: int,
        column: int = 0,
        columnspan: int = 1,
    ):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["surface"],
            corner_radius=CARD_RADIUS,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(
            row=row,
            column=column,
            columnspan=columnspan,
            padx=(0, 8) if column == 0 and columnspan == 1 else (8, 0) if column == 1 else 0,
            pady=(0, 12),
            sticky="nsew",
        )
        card.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=title,
            anchor="w",
            font=ctk.CTkFont(size=FONT_SECTION, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, sticky="w")
        if subtitle:
            ctk.CTkLabel(
                header,
                text=subtitle,
                anchor="w",
                justify="left",
                wraplength=720,
                font=ctk.CTkFont(size=FONT_SMALL),
                text_color=COLORS["muted"],
            ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        body.grid_columnconfigure(0, weight=1)
        return card, body

    def _collapsible(
        self,
        parent,
        key: str,
        title: str,
        subtitle: str,
        *,
        row: int,
        columnspan: int = 2,
    ):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["surface"],
            corner_radius=CARD_RADIUS,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(
            row=row,
            column=0,
            columnspan=columnspan,
            pady=(0, 12),
            sticky="ew",
        )
        card.grid_columnconfigure(0, weight=1)
        expanded = self.section_state.get(key, False)
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=16)
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=title,
            anchor="w",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text=subtitle,
            anchor="w",
            justify="left",
            font=ctk.CTkFont(size=FONT_SMALL),
            text_color=COLORS["muted"],
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ctk.CTkButton(
            header,
            text=f"{'⌃' if expanded else '⌄'}  {self.t('collapse') if expanded else self.t('expand')}",
            width=84,
            height=38,
            corner_radius=CONTROL_RADIUS,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=FONT_SMALL),
            command=lambda: self._toggle_section(key),
        ).grid(row=0, column=1, rowspan=2, sticky="e")
        if not expanded:
            return card, None

        divider = ctk.CTkFrame(card, height=1, fg_color=COLORS["border"])
        divider.grid(row=1, column=0, sticky="ew")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=2, column=0, sticky="ew", padx=20, pady=18)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        return card, body

    def _toggle_section(self, key: str) -> None:
        self.section_state[key] = not self.section_state.get(key, False)
        self._show_page(self.current_page)

    def _field(
        self,
        parent,
        label: str,
        variable,
        *,
        row: int,
        column: int = 0,
        columnspan: int = 1,
        show: str | None = None,
        button_text: str | None = None,
        button_command: Callable | None = None,
        button_width: int = 92,
    ):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(
            row=row,
            column=column,
            columnspan=columnspan,
            padx=(0, 8) if column == 0 and columnspan == 1 else (8, 0) if column == 1 else 0,
            pady=6,
            sticky="ew",
        )
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            wrap,
            text=label,
            anchor="w",
            font=ctk.CTkFont(size=FONT_SMALL, weight="bold"),
            text_color=COLORS["muted"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
        entry = ctk.CTkEntry(
            wrap,
            textvariable=variable,
            height=INPUT_HEIGHT,
            corner_radius=CONTROL_RADIUS,
            border_width=1,
            border_color=COLORS["border"],
            fg_color=COLORS["surface_alt"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=FONT_BODY),
            show=show,
        )
        entry.grid(row=1, column=0, sticky="ew")
        button = None
        if button_text and button_command:
            button = ctk.CTkButton(
                wrap,
                text=button_text,
                width=button_width,
                height=INPUT_HEIGHT,
                corner_radius=CONTROL_RADIUS,
                fg_color=COLORS["surface_alt"],
                hover_color=COLORS["surface_hover"],
                border_width=1,
                border_color=COLORS["border"],
                text_color=COLORS["text"],
                font=ctk.CTkFont(size=FONT_BODY, weight="bold"),
                command=button_command,
            )
            button.grid(row=1, column=1, padx=(8, 0))
        return entry, button

    def _primary_button(self, parent, text: str, command: Callable, *, danger: bool = False):
        idle_fg = COLORS["danger"] if danger else COLORS["primary"]
        idle_hover = COLORS["danger_hover"] if danger else COLORS["primary_hover"]
        idle_text_color = "#FFFFFF" if danger else COLORS["primary_text"]
        busy = self.busy
        # Busy look: gray fill + body text (high contrast). Avoid CTk
        # state=disabled — it washes text to gray-on-gray and becomes unreadable.
        button = ctk.CTkButton(
            parent,
            text=self.t("starting") if busy else text,
            height=BTN_HEIGHT,
            corner_radius=CONTROL_RADIUS,
            fg_color=COLORS["surface_hover"] if busy else idle_fg,
            hover_color=COLORS["surface_hover"] if busy else idle_hover,
            text_color=COLORS["text"] if busy else idle_text_color,
            font=ctk.CTkFont(size=FONT_BODY, weight="bold"),
            command=(lambda: None) if busy else command,
        )
        self._busy_buttons.append(
            {
                "widget": button,
                "idle_text": text,
                "idle_fg": idle_fg,
                "idle_hover": idle_hover,
                "idle_text_color": idle_text_color,
                "idle_command": command,
            }
        )
        return button

    def _set_busy(self, busy: bool, *, label: str | None = None) -> None:
        self.busy = busy
        busy_text = label or self.t("starting")
        living: list[dict] = []
        for item in self._busy_buttons:
            button = item["widget"]
            try:
                if not button.winfo_exists():
                    continue
                if busy:
                    button.configure(
                        text=busy_text,
                        fg_color=COLORS["surface_hover"],
                        hover_color=COLORS["surface_hover"],
                        text_color=COLORS["text"],
                        command=lambda: None,
                    )
                else:
                    button.configure(
                        text=item["idle_text"],
                        fg_color=item["idle_fg"],
                        hover_color=item["idle_hover"],
                        text_color=item["idle_text_color"],
                        command=item["idle_command"],
                    )
                living.append(item)
            except Exception:
                continue
        self._busy_buttons = living

    def _secondary_button(self, parent, text: str, command: Callable):
        return ctk.CTkButton(
            parent,
            text=text,
            height=BTN_HEIGHT,
            corner_radius=CONTROL_RADIUS,
            fg_color="transparent",
            hover_color=COLORS["surface_hover"],
            border_width=1,
            border_color=COLORS["border_strong"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=FONT_BODY, weight="bold"),
            command=command,
        )

    def _metric(self, parent, title: str, value: str, *, row: int, column: int):
        frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS["surface_alt"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        frame.grid(row=row, column=column, padx=5, pady=5, sticky="nsew")
        parent.grid_columnconfigure(column, weight=1)
        ctk.CTkLabel(
            frame,
            text=title,
            anchor="w",
            font=ctk.CTkFont(size=FONT_CAPTION, weight="bold"),
            text_color=COLORS["muted"],
        ).pack(fill="x", padx=12, pady=(11, 3))
        ctk.CTkLabel(
            frame,
            text=value,
            anchor="w",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text"],
        ).pack(fill="x", padx=12, pady=(0, 11))

    def _build_home(self) -> None:
        page = self._page()

        _, workspace = self._card(
            page,
            self.t("workspace"),
            self.t("workspace_hint"),
            row=0,
            columnspan=2,
        )
        self._field(
            workspace,
            self.t("repository"),
            self.repo_var,
            row=0,
            columnspan=2,
            button_text=self.t("browse"),
            button_command=self._browse_repo,
        )
        summary = ctk.CTkFrame(workspace, fg_color="transparent")
        summary.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for text in (
            f"{self.t('current_branch')}: {self._git_branch()}",
            f"{self.t('mode')}: {self.mode_var.get()}",
            f"{self.t('transport')}: {self.transport_var.get()}",
        ):
            ctk.CTkLabel(
                summary,
                text=text,
                height=27,
                corner_radius=8,
                fg_color=COLORS["surface_alt"],
                text_color=COLORS["muted"],
                font=ctk.CTkFont(size=FONT_CAPTION, weight="bold"),
            ).pack(side="left", padx=(0, 7))

        _, access = self._card(
            page,
            self.t("access_mode"),
            self.t("access_hint"),
            row=1,
            column=0,
        )
        labels = [self.t("mode_read"), self.t("mode_write"), self.t("mode_test")]
        mapping = dict(zip(labels, ("read", "write", "test")))
        reverse = {value: key for key, value in mapping.items()}
        selector = ctk.CTkSegmentedButton(
            access,
            values=labels,
            height=44,
            selected_color=COLORS["accent_soft"],
            selected_hover_color=COLORS["surface_hover"],
            unselected_color=COLORS["surface_alt"],
            unselected_hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=FONT_BODY),
            command=lambda value: self.mode_var.set(mapping[value]),
        )
        selector.set(reverse[self.mode_var.get()])
        selector.grid(row=0, column=0, sticky="ew")

        _, transport = self._card(
            page,
            self.t("transport"),
            self.t("transport_hint"),
            row=1,
            column=1,
        )
        transport_selector = ctk.CTkSegmentedButton(
            transport,
            values=[self.t("stdio"), self.t("http")],
            height=44,
            selected_color=COLORS["accent_soft"],
            selected_hover_color=COLORS["surface_hover"],
            unselected_color=COLORS["surface_alt"],
            unselected_hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=FONT_BODY),
            command=self._transport_changed,
        )
        transport_selector.set(
            self.t("stdio") if self.transport_var.get() == "stdio" else self.t("http")
        )
        transport_selector.grid(row=0, column=0, sticky="ew")

        next_row = 2
        if self.transport_var.get() == "streamable-http":
            _, http_body = self._collapsible(
                page,
                "home_http",
                self.t("http_settings"),
                self.t("http_settings_hint"),
                row=next_row,
            )
            if http_body is not None:
                self._field(http_body, self.t("http_host"), self.http_host_var, row=0, column=0)
                self._field(http_body, self.t("http_port"), self.http_port_var, row=0, column=1)
                self._field(http_body, self.t("http_path"), self.http_path_var, row=1, column=0)
                self._field(
                    http_body,
                    self.t("http_token"),
                    self.http_token_var,
                    row=1,
                    column=1,
                    show="" if self.token_visible else "•",
                )
                token_actions = ctk.CTkFrame(http_body, fg_color="transparent")
                token_actions.grid(row=2, column=0, columnspan=2, sticky="e", pady=(8, 0))
                self._secondary_button(
                    token_actions,
                    self.t("hide") if self.token_visible else self.t("show"),
                    self._toggle_token,
                ).pack(side="left", padx=4)
                self._secondary_button(
                    token_actions,
                    self.t("regenerate"),
                    self._generate_token,
                ).pack(side="left", padx=4)
                self._field(
                    http_body,
                    self.t("http_allowed_hosts"),
                    self.allowed_hosts_var,
                    row=3,
                    column=0,
                )
                self._field(
                    http_body,
                    self.t("http_allowed_origins"),
                    self.allowed_origins_var,
                    row=3,
                    column=1,
                )
                self._field(
                    http_body,
                    self.t("http_public_url"),
                    self.http_public_url_var,
                    row=4,
                    columnspan=2,
                )
                self._field(
                    http_body,
                    self.t("http_tls_cert"),
                    self.http_tls_cert_var,
                    row=5,
                    column=0,
                )
                self._field(
                    http_body,
                    self.t("http_tls_key"),
                    self.http_tls_key_var,
                    row=5,
                    column=1,
                )
                self._field(
                    http_body,
                    self.t("http_tls_ca"),
                    self.http_tls_ca_var,
                    row=6,
                    column=0,
                )
                self._field(
                    http_body,
                    self.t("http_proxy_ips"),
                    self.http_proxy_ips_var,
                    row=6,
                    column=1,
                )
                self._field(
                    http_body,
                    self.t("http_client_cert"),
                    self.http_client_cert_var,
                    row=7,
                    column=0,
                )
                self._field(
                    http_body,
                    self.t("http_client_key"),
                    self.http_client_key_var,
                    row=7,
                    column=1,
                )
                self._field(
                    http_body,
                    self.t("http_request_kb"),
                    self.http_request_kb_var,
                    row=8,
                    column=0,
                )
                http_flags = ctk.CTkFrame(http_body, fg_color="transparent")
                http_flags.grid(row=8, column=1, sticky="ew", padx=(8, 0), pady=6)
                for text, variable in (
                    (self.t("http_tls_proxy"), self.http_tls_proxy_var),
                    (self.t("http_json_response"), self.http_json_var),
                    (self.t("http_stateless"), self.http_stateless_var),
                ):
                    ctk.CTkSwitch(
                        http_flags,
                        text=text,
                        variable=variable,
                        progress_color=COLORS["primary"],
                        text_color=COLORS["text"],
                        font=ctk.CTkFont(size=FONT_SMALL),
                    ).pack(anchor="w", pady=3)
            next_row += 1

        _, advanced = self._collapsible(
            page,
            "home_advanced",
            self.t("advanced"),
            self.t("advanced_hint"),
            row=next_row,
        )
        if advanced is not None:
            self._field(advanced, self.t("max_file"), self.max_file_var, row=0, column=0)
            self._field(advanced, self.t("max_patch"), self.max_patch_var, row=0, column=1)
            self._field(advanced, self.t("max_search"), self.max_search_var, row=1, column=0)
            self._field(advanced, self.t("max_output"), self.max_output_var, row=1, column=1)
            self._field(advanced, self.t("test_timeout"), self.test_timeout_var, row=2, column=0)
            self._field(advanced, self.t("audit_log"), self.audit_var, row=2, column=1)
            self._field(
                advanced,
                self.t("mcp_log"),
                self.mcp_log_var,
                row=3,
                columnspan=2,
            )
            self._field(
                advanced,
                self.t("log_max_kb"),
                self.log_max_kb_var,
                row=4,
                column=0,
            )
            self._field(
                advanced,
                self.t("log_backup_count"),
                self.log_backup_var,
                row=4,
                column=1,
            )
            self._field(advanced, self.t("test_max_images"), self.test_max_images_var, row=5, column=0)
            self._field(advanced, self.t("test_image_max_kb"), self.test_image_max_kb_var, row=5, column=1)
            self._field(advanced, self.t("test_image_total_kb"), self.test_image_total_kb_var, row=6, column=0)
            self._field(advanced, self.t("read_image_max_kb"), self.read_image_max_kb_var, row=6, column=1)
            self._field(advanced, self.t("test_artifact_dir"), self.test_artifact_dir_var, row=7, columnspan=2)
            warning = ctk.CTkFrame(
                advanced,
                fg_color=COLORS["warning_soft"],
                corner_radius=10,
            )
            warning.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(10, 0))
            ctk.CTkSwitch(
                warning,
                text=self.t("dirty_worktree"),
                variable=self.dirty_var,
                progress_color=COLORS["warning"],
                button_color=COLORS["surface"],
                button_hover_color=COLORS["surface"],
                text_color=COLORS["text"],
                font=ctk.CTkFont(size=FONT_BODY),
            ).pack(anchor="w", padx=12, pady=(11, 3))
            ctk.CTkLabel(
                warning,
                text=self.t("dirty_warning"),
                text_color=COLORS["muted"],
                font=ctk.CTkFont(size=FONT_SMALL),
            ).pack(anchor="w", padx=12, pady=(0, 11))
            warning.grid_configure(row=8)

            commit_box = ctk.CTkFrame(
                advanced,
                fg_color=COLORS["warning_soft"],
                corner_radius=10,
            )
            commit_box.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(10, 0))
            ctk.CTkSwitch(
                commit_box,
                text=self.t("git_commit"),
                variable=self.git_commit_var,
                progress_color=COLORS["warning"],
                button_color=COLORS["surface"],
                button_hover_color=COLORS["surface"],
                text_color=COLORS["text"],
                font=ctk.CTkFont(size=FONT_BODY),
            ).pack(anchor="w", padx=12, pady=(11, 3))
            ctk.CTkLabel(
                commit_box,
                text=self.t("git_commit_warning"),
                text_color=COLORS["muted"],
                font=ctk.CTkFont(size=FONT_SMALL),
            ).pack(anchor="w", padx=12, pady=(0, 11))

        action_bar = ctk.CTkFrame(
            page,
            fg_color=COLORS["surface"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )
        action_bar.grid(
            row=next_row + 1,
            column=0,
            columnspan=2,
            pady=(2, 10),
            sticky="ew",
        )
        ctk.CTkLabel(
            action_bar,
            text=self._repo_name(),
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=FONT_SMALL),
        ).pack(side="left", padx=16, pady=13)
        if self.transport_var.get() == "stdio":
            self._primary_button(
                action_bar,
                self.t("connect"),
                self._run_smoke_test,
            ).pack(side="right", padx=(6, 14), pady=9)
        else:
            self._primary_button(
                action_bar,
                self.t("stop_http") if self.processes.mcp.running else self.t("start_http"),
                self._stop_http if self.processes.mcp.running else self._start_http,
                danger=self.processes.mcp.running,
            ).pack(side="right", padx=(6, 14), pady=9)

    def _build_server(self) -> None:
        server_workspace.build(self)

    def _build_chatgpt(self) -> None:
        page = self._page()
        _, setup = self._card(
            page,
            self.t("tunnel_setup"),
            self.t("tunnel_setup_hint"),
            row=0,
            columnspan=2,
        )
        self._field(setup, self.t("tunnel_client"), self.tunnel_path_var, row=0, column=0)
        self._field(setup, self.t("profile"), self.tunnel_profile_var, row=0, column=1)
        self._field(setup, self.t("tunnel_id"), self.tunnel_id_var, row=1, column=0)
        self._api_key_entry, self._api_key_toggle_btn = self._field(
            setup,
            self.t("api_key"),
            self.api_key_var,
            row=1,
            column=1,
            show="" if self.api_key_visible else "•",
            button_text="🙈" if self.api_key_visible else "👁",
            button_command=self._toggle_api_key,
            button_width=44,
        )
        self._field(
            setup,
            self.t("profile_path"),
            self.tunnel_profile_path_var,
            row=2,
            columnspan=2,
        )
        setup.grid_columnconfigure(
            0,
            weight=FORM_PRIMARY_WEIGHT,
            minsize=360,
            uniform="tunnel-fields",
        )
        setup.grid_columnconfigure(
            1,
            weight=FORM_SECONDARY_WEIGHT,
            minsize=260,
            uniform="tunnel-fields",
        )

        controls = ctk.CTkFrame(setup, fg_color="transparent")
        controls.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        start_button = self._primary_button(
            controls,
            self.t("stop_tunnel") if self.processes.tunnel.running else self.t("start_tunnel"),
            self._stop_tunnel if self.processes.tunnel.running else self._start_tunnel,
            danger=self.processes.tunnel.running,
        )
        controls.grid_columnconfigure(0, weight=1)
        start_button.grid(row=0, column=0, sticky="ew")

        _, tunnel_advanced = self._collapsible(
            page,
            "chatgpt_advanced",
            self.t("tunnel_advanced"),
            self.t("tunnel_advanced_hint"),
            row=1,
            columnspan=2,
        )
        if tunnel_advanced is not None:
            self._field(
                tunnel_advanced,
                self.t("tunnel_http_proxy"),
                self.tunnel_http_proxy_var,
                row=0,
                columnspan=2,
            )

        _, status_body = self._card(
            page,
            self.t("tunnel_status"),
            self.t("tunnel_ready"),
            row=2,
            columnspan=2,
        )
        metrics = ctk.CTkFrame(status_body, fg_color="transparent")
        metrics.grid(row=0, column=0, sticky="ew")
        self._metric(
            metrics,
            self.t("status"),
            self.t("running") if self.processes.tunnel.running else self.t("stopped"),
            row=0,
            column=0,
        )
        self._metric(metrics, self.t("pid"), str(self.processes.tunnel.pid or "—"), row=0, column=1)
        self._metric(metrics, self.t("uptime"), format_uptime(self.processes.tunnel.uptime), row=0, column=2)
        self._metric(metrics, self.t("transport"), self.transport_var.get(), row=0, column=3)

        _, auth_body = self._collapsible(
            page,
            "chatgpt_auth",
            self.t("auth_boundary"),
            self.t("auth_boundary_hint"),
            row=3,
        )
        if auth_body is not None:
            info = ctk.CTkFrame(auth_body, fg_color=COLORS["primary_soft"], corner_radius=10)
            info.grid(row=0, column=0, columnspan=2, sticky="ew")
            ctk.CTkLabel(
                info,
                text=self.t("auth_explanation"),
                justify="left",
                wraplength=760,
                text_color=COLORS["text"],
                font=ctk.CTkFont(size=FONT_BODY),
            ).pack(anchor="w", padx=14, pady=13)
            if self.transport_var.get() == "streamable-http":
                ctk.CTkLabel(
                    auth_body,
                    text=self.t("http_tunnel_note"),
                    justify="left",
                    wraplength=760,
                    text_color=COLORS["warning"],
                    font=ctk.CTkFont(size=FONT_BODY, weight="bold"),
                ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def _build_logs_center(self) -> None:
        log_workspace.build(self)

    def _build_about(self) -> None:
        page = self._page()
        _, intro = self._card(
            page,
            "Local Repo MCP",
            self.t("about_desc"),
            row=0,
            columnspan=2,
        )
        ctk.CTkLabel(
            intro,
            text=f"{self.t('version')} {VERSION}",
            height=30,
            corner_radius=9,
            fg_color=COLORS["primary_soft"],
            text_color=COLORS["primary"],
            font=ctk.CTkFont(size=FONT_SMALL, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        self._secondary_button(
            intro,
            self.t("github"),
            lambda: webbrowser.open(GITHUB_URL),
        ).grid(row=0, column=1, sticky="e")

        _, capabilities = self._card(
            page,
            self.t("capabilities"),
            "",
            row=1,
            columnspan=2,
        )
        for index, (icon, text) in enumerate(
            (
                ("↳", self.t("cap_read")),
                ("±", self.t("cap_patch")),
                ("●", self.t("cap_commit")),
                ("✓", self.t("cap_test")),
                ("⌁", self.t("cap_transport")),
            )
        ):
            frame = ctk.CTkFrame(capabilities, fg_color=COLORS["surface_alt"], corner_radius=10)
            frame.grid(row=index // 2, column=index % 2, padx=5, pady=5, sticky="ew")
            capabilities.grid_columnconfigure(index % 2, weight=1)
            ctk.CTkLabel(
                frame,
                text=f"{icon}   {text}",
                anchor="w",
                text_color=COLORS["text"],
                font=ctk.CTkFont(size=FONT_BODY, weight="bold"),
            ).pack(fill="x", padx=14, pady=13)

        _, security = self._collapsible(
            page,
            "about_security",
            self.t("security_boundary"),
            self.t("security_boundary_hint"),
            row=2,
        )
        if security is not None:
            for index, item in enumerate(self.t("boundary_items").splitlines()):
                ctk.CTkLabel(
                    security,
                    text=f"•  {item}",
                    anchor="w",
                    text_color=COLORS["text"],
                    font=ctk.CTkFont(size=FONT_BODY),
                ).grid(row=index, column=0, columnspan=2, sticky="w", pady=4)

    def _code_box(
        self, parent, text: str, *, height: int, tail: bool = False
    ):
        box = ctk.CTkTextbox(
            parent,
            height=height,
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
            fg_color=COLORS["code"],
            text_color=COLORS["text"],
            font=("Consolas" if os.name == "nt" else "monospace", FONT_BODY),
            wrap="word",
        )
        box.insert("1.0", text)
        box.configure(state="disabled")
        if tail:
            box.see("end")
        return box

    def _collect_config(self, *, quiet: bool = False) -> AppConfig | None:
        # Pre-validate numeric fields with field-specific error messages.
        numeric_fields = {
            "http_port": (self.http_port_var.get(), 1, 65535),
            "http_request_kb": (self.http_request_kb_var.get(), 1, 5000),
            "max_file": (self.max_file_var.get(), 1, 20000),
            "max_patch": (self.max_patch_var.get(), 1, 5000),
            "max_search": (self.max_search_var.get(), 1, 1000),
            "max_output": (self.max_output_var.get(), 1, 2000),
            "log_max_kb": (self.log_max_kb_var.get(), 64, 100000),
            "log_backup_count": (self.log_backup_var.get(), 1, 20),
            "test_timeout": (self.test_timeout_var.get(), 1, 1800),
            "test_max_images": (self.test_max_images_var.get(), 1, 20),
            "test_image_max_kb": (self.test_image_max_kb_var.get(), 1, 8192),
            "test_image_total_kb": (self.test_image_total_kb_var.get(), 1, 8192),
            "read_image_max_kb": (self.read_image_max_kb_var.get(), 1, 8192),
        }
        for field, (raw, low, high) in numeric_fields.items():
            try:
                value = int(raw.strip() or "0")
            except ValueError:
                if not quiet:
                    messagebox.showerror(
                        self.t("error"),
                        f"{self.t(field)}: {self.t('numeric_invalid')}",
                    )
                return None
            if not low <= value <= high:
                if not quiet:
                    messagebox.showerror(
                        self.t("error"),
                        f"{self.t(field)}: {self.t('numeric_out_of_range')} ({low}–{high})",
                    )
                return None

        try:
            cfg = AppConfig(
                language=self.config_data.language,
                appearance=self.config_data.appearance,
                repo_root=self.repo_var.get().strip(),
                mcp_mode=self.mode_var.get(),
                transport=self.transport_var.get(),
                http_host=self.http_host_var.get().strip() or "127.0.0.1",
                http_port=int(self.http_port_var.get()),
                http_path=self.http_path_var.get().strip() or "/mcp",
                http_auth_mode="bearer",
                http_auth_token=self.http_token_var.get().strip(),
                http_allowed_hosts=self.allowed_hosts_var.get().strip(),
                http_allowed_origins=self.allowed_origins_var.get().strip(),
                http_public_url=self.http_public_url_var.get().strip(),
                http_tls_certfile=self.http_tls_cert_var.get().strip(),
                http_tls_keyfile=self.http_tls_key_var.get().strip(),
                http_tls_client_ca=self.http_tls_ca_var.get().strip(),
                http_client_certfile=self.http_client_cert_var.get().strip(),
                http_client_keyfile=self.http_client_key_var.get().strip(),
                http_tls_terminated_proxy=self.http_tls_proxy_var.get(),
                http_proxy_trusted_ips=self.http_proxy_ips_var.get().strip(),
                http_max_request_bytes=int(self.http_request_kb_var.get()) * 1000,
                http_json_response=self.http_json_var.get(),
                http_stateless=self.http_stateless_var.get(),
                max_file_bytes=int(self.max_file_var.get()) * 1000,
                max_patch_bytes=int(self.max_patch_var.get()) * 1000,
                max_search_results=int(self.max_search_var.get()),
                max_output_bytes=int(self.max_output_var.get()) * 1000,
                allow_dirty_worktree=self.dirty_var.get(),
                allow_git_commit=self.git_commit_var.get(),
                audit_log=self.audit_var.get().strip(),
                mcp_log=self.mcp_log_var.get().strip(),
                log_max_bytes=int(self.log_max_kb_var.get()) * 1000,
                log_backup_count=int(self.log_backup_var.get()),
                test_timeout_max=int(self.test_timeout_var.get()),
                test_artifact_dir=self.test_artifact_dir_var.get().strip(),
                max_test_images=int(self.test_max_images_var.get()),
                max_test_image_bytes=int(self.test_image_max_kb_var.get()) * 1024,
                max_test_image_total_bytes=int(self.test_image_total_kb_var.get()) * 1024,
                max_read_image_bytes=int(self.read_image_max_kb_var.get()) * 1024,
                tunnel_client_path=self.tunnel_path_var.get().strip() or "tunnel-client",
                tunnel_id=self.tunnel_id_var.get().strip(),
                tunnel_profile=self.tunnel_profile_var.get().strip() or "local-repo",
                tunnel_profile_path=self.tunnel_profile_path_var.get().strip(),
                tunnel_http_proxy=self.tunnel_http_proxy_var.get().strip(),
                control_plane_api_key=self.api_key_var.get().strip(),
            )
        except ValueError:
            if not quiet:
                messagebox.showerror(self.t("error"), self.t("numeric_invalid"))
            return None

        if cfg.transport == "streamable-http":
            cfg.http_auth_mode = "bearer"
            cfg.ensure_http_token()
            self.http_token_var.set(cfg.http_auth_token)

        errors = cfg.validate()
        if errors:
            if not quiet:
                messagebox.showerror(
                    self.t("error"),
                    "\n".join("• " + self.t(key) for key in errors),
                )
            return None
        return cfg

    def _save(self) -> AppConfig | None:
        cfg = self._collect_config()
        if cfg is None:
            return None
        save_config(cfg)
        self.config_data = cfg
        self._status(self.t("saved"), "success")
        return cfg

    def _start_http(self) -> None:
        cfg = self._save()
        if cfg is not None:
            self._background(
                lambda: self.processes.start_http(cfg),
                self.t("running"),
                rebuild=True,
                busy_label=self.t("starting_http"),
            )

    def _stop_http(self) -> None:
        self._background(
            self.processes.mcp.stop,
            self.t("stopped"),
            rebuild=True,
            busy_label=self.t("stopping_http"),
        )

    def _run_smoke_test(self) -> None:
        cfg = self._save()
        if cfg is None:
            return
        if cfg.transport == "streamable-http" and not self.processes.mcp.running:
            messagebox.showerror(self.t("error"), self.t("start_http_first"))
            return

        def success(value):
            self.last_test = value
            self._status(self.t("connected"), "success")
            self._show_page("server")

        self._background(
            lambda: run_smoke_test(
                cfg, log_callback=self.processes.mcp.append_log
            ),
            on_success=success,
            busy_label=self.t("connecting"),
        )

    def _start_tunnel(self) -> None:
        cfg = self._save()
        if cfg:
            self._background(
                lambda: self.tunnel.start(cfg),
                self.t("tunnel_connected"),
                rebuild=True,
                busy_label=self.t("starting_tunnel"),
            )

    def _stop_tunnel(self) -> None:
        self._background(
            self.processes.tunnel.stop,
            self.t("stopped"),
            rebuild=True,
            busy_label=self.t("stopping_tunnel"),
        )

    def _background(
        self,
        task: Callable,
        message: str | None = None,
        *,
        on_success: Callable | None = None,
        rebuild: bool = False,
        busy_label: str | None = None,
    ) -> None:
        if self.busy:
            return
        label = busy_label or self.t("starting")
        self._set_busy(True, label=label)
        self._status(label, "working")

        def worker():
            try:
                result = task()
            except Exception as exc:
                self.after(0, lambda error=str(exc): self._failed(error))
                return
            self.after(
                0,
                lambda: self._succeeded(result, message, on_success, rebuild),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _failed(self, error: str) -> None:
        self._set_busy(False)
        self._status(self.t("error"), "danger")
        show_result_dialog(
            self,
            title=self.t("error"),
            message=error,
            kind="error",
            copy_label=self.t("copy"),
            ok_label=self.t("ok"),
        )

    def _succeeded(self, result, message, callback, rebuild) -> None:
        self._set_busy(False)
        if callback:
            callback(result)
        elif message:
            self._status(message, "success")
        if rebuild:
            self._show_page(self.current_page)

    def _show_result(self, value: str) -> None:
        show_result_dialog(
            self,
            title=self.t("success"),
            message=value,
            kind="success",
            copy_label=self.t("copy"),
            ok_label=self.t("ok"),
        )

    def _status(self, text: str, kind: str = "neutral") -> None:
        palette = {
            "neutral": (COLORS["surface_alt"], COLORS["muted"]),
            "working": (COLORS["primary_soft"], COLORS["primary"]),
            "success": (COLORS["success_soft"], COLORS["success"]),
            "danger": (COLORS["danger_soft"], COLORS["danger"]),
        }
        background, foreground = palette[kind]
        self.banner.configure(text=text, fg_color=background, text_color=foreground)

    def _transport_changed(self, value: str) -> None:
        selected = "stdio" if value == self.t("stdio") else "streamable-http"
        if self.processes.mcp.running and selected != self.transport_var.get():
            messagebox.showwarning(self.t("warning"), self.t("stop_http_first"))
            return
        self.transport_var.set(selected)
        if selected == "streamable-http" and not self.http_token_var.get():
            self._generate_token(rebuild=False)
        self._show_page("home")

    def _generate_token(self, rebuild: bool = True) -> None:
        import secrets

        self.http_token_var.set(secrets.token_urlsafe(32))
        if rebuild:
            self._show_page("home")

    def _toggle_token(self) -> None:
        self.token_visible = not self.token_visible
        self._show_page("home")

    def _toggle_api_key(self) -> None:
        self.api_key_visible = not self.api_key_visible
        entry = self._api_key_entry
        button = self._api_key_toggle_btn
        if entry is None or button is None:
            return
        try:
            if not entry.winfo_exists():
                return
        except Exception:
            return
        entry.configure(show="" if self.api_key_visible else "•")
        button.configure(text="🙈" if self.api_key_visible else "👁")

    def _browse_repo(self) -> None:
        path = filedialog.askdirectory(initialdir=self.repo_var.get() or str(ROOT))
        if path:
            self.repo_var.set(path)
            self._show_page("home")

    def _repo_name(self) -> str:
        raw = self.repo_var.get().strip()
        return Path(raw).name if raw else self.t("not_selected")

    def _git_branch(self) -> str:
        raw = self.repo_var.get().strip()
        if not raw:
            return "—"
        info = inspect_worktree(raw)
        return info.branch if info.ready else "—"

    def _client_config_text(self) -> str:
        cfg = self._collect_config(quiet=True)
        if cfg is None:
            return ""
        if cfg.transport == "streamable-http":
            return json.dumps(
                {
                    "mcpServers": {
                        "local-repo": {
                            "url": cfg.endpoint_url(),
                            "transport": "streamable-http",
                            "headers": {
                                "Authorization": "Bearer <LOCAL_REPO_MCP_TOKEN>"
                            },
                        }
                    }
                },
                indent=2,
            )

        env = cfg.mcp_env()
        env["MCP_TRANSPORT"] = "stdio"
        env.pop("HTTP_AUTH_TOKEN", None)
        command = launcher_command()
        return json.dumps(
            {
                "mcpServers": {
                    "local-repo": {
                        "command": command[0],
                        "args": command[1:],
                        "env": env,
                    }
                }
            },
            indent=2,
        )

    def _copy_text(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self._status(self.t("copied"), "success")

    def _change_language(self, value: str) -> None:
        self.config_data.language = "zh" if value == "中文" else "en"
        save_config(self.config_data)
        self._build_shell()
        self._show_page(self.current_page)

    def _change_appearance(self, value: str) -> None:
        reverse = {
            self.t("system"): "system",
            self.t("light"): "light",
            self.t("dark"): "dark",
        }
        selected = reverse[value]
        self.config_data.appearance = selected
        ctk.set_appearance_mode(selected)
        save_config(self.config_data)
        self._build_shell()
        self._show_page(self.current_page)

    def _on_close(self) -> None:
        if self.processes.mcp.running or self.processes.tunnel.running:
            if not messagebox.askyesno(self.t("confirm"), self.t("exit_confirm")):
                return
        self.processes.stop_all()
        self.destroy()

