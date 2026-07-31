from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from gui.config import AppConfig, load_config, save_config
from gui.i18n import tr
from gui.process_manager import ProcessManager, format_uptime
from gui.smoke_test import run_smoke_test
from gui.theme import COLORS
from gui.tunnel_manager import TunnelManager

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.1.0"
GITHUB_URL = "https://github.com/cloud-Xolt/local-repo-mcp"


class LocalRepoMCPApp(ctk.CTk):
    def __init__(self) -> None:
        self.config_data = load_config()
        ctk.set_appearance_mode(self.config_data.appearance)
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.title("Local Repo MCP")
        self.geometry("1180x780")
        self.minsize(980, 680)
        self.configure(fg_color=COLORS["bg"])

        self.processes = ProcessManager()
        self.tunnel = TunnelManager(self.processes)
        self.current_page = "home"
        self.busy = False
        self.advanced_open = False
        self.last_test: dict | None = None
        self.status_message = self.t("ready")
        self._vars_ready = False

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._init_variables()
        self._build_shell()
        self._show_page("home")
        self.after(800, self._periodic_refresh)

    def t(self, key: str) -> str:
        return tr(self.config_data.language, key)

    def _init_variables(self) -> None:
        self.repo_var = ctk.StringVar(value=self.config_data.repo_root)
        self.mode_var = ctk.StringVar(value=self.config_data.mcp_mode)
        self.transport_var = ctk.StringVar(value=self.config_data.transport)
        self.http_host_var = ctk.StringVar(value=self.config_data.http_host)
        self.http_port_var = ctk.StringVar(value=str(self.config_data.http_port))
        self.http_path_var = ctk.StringVar(value=self.config_data.http_path)
        self.http_auth_var = ctk.StringVar(value=self.config_data.http_auth_mode)
        self.http_token_var = ctk.StringVar(value=self.config_data.http_auth_token)
        self.allowed_hosts_var = ctk.StringVar(value=self.config_data.http_allowed_hosts)
        self.allowed_origins_var = ctk.StringVar(value=self.config_data.http_allowed_origins)
        self.max_request_var = ctk.StringVar(value=str(self.config_data.http_max_request_bytes // 1024))
        self.json_response_var = ctk.BooleanVar(value=self.config_data.http_json_response)
        self.stateless_var = ctk.BooleanVar(value=self.config_data.http_stateless)

        self.max_file_var = ctk.StringVar(value=str(self.config_data.max_file_bytes // 1000))
        self.max_patch_var = ctk.StringVar(value=str(self.config_data.max_patch_bytes // 1000))
        self.max_search_var = ctk.StringVar(value=str(self.config_data.max_search_results))
        self.max_output_var = ctk.StringVar(value=str(self.config_data.max_output_bytes // 1000))
        self.dirty_var = ctk.BooleanVar(value=self.config_data.allow_dirty_worktree)
        self.audit_var = ctk.StringVar(value=self.config_data.audit_log)
        self.test_timeout_var = ctk.StringVar(value=str(self.config_data.test_timeout_max))

        self.tunnel_path_var = ctk.StringVar(value=self.config_data.tunnel_client_path)
        self.tunnel_id_var = ctk.StringVar(value=self.config_data.tunnel_id)
        self.tunnel_profile_var = ctk.StringVar(value=self.config_data.tunnel_profile)
        self.api_key_var = ctk.StringVar(value=self.config_data.control_plane_api_key)
        self.api_key_visible = False
        self.http_token_visible = False
        self._vars_ready = True

    def _build_shell(self) -> None:
        for child in self.winfo_children():
            child.destroy()

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=COLORS["sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        brand = ctk.CTkLabel(
            self.sidebar, text="◈  Local Repo MCP", font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#FFFFFF", anchor="w",
        )
        brand.pack(fill="x", padx=22, pady=(26, 28))

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for key in ("home", "server", "chatgpt", "logs", "about"):
            button = ctk.CTkButton(
                self.sidebar, text=self.t(key), anchor="w", height=42,
                fg_color="transparent", hover_color="#1F2937", text_color="#CBD5E1",
                font=ctk.CTkFont(size=14), command=lambda value=key: self._show_page(value),
            )
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[key] = button

        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        preference = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        preference.pack(fill="x", padx=14, pady=16)
        ctk.CTkLabel(preference, text=self.t("language"), text_color="#94A3B8", anchor="w").pack(fill="x")
        language = ctk.CTkSegmentedButton(
            preference, values=["中文", "English"], height=30,
            command=self._change_language,
        )
        language.set("中文" if self.config_data.language == "zh" else "English")
        language.pack(fill="x", pady=(5, 12))

        ctk.CTkLabel(preference, text=self.t("appearance"), text_color="#94A3B8", anchor="w").pack(fill="x")
        appearance_values = [self.t("system"), self.t("light"), self.t("dark")]
        appearance = ctk.CTkOptionMenu(
            preference, values=appearance_values, height=30,
            command=self._change_appearance,
        )
        appearance.set({
            "system": self.t("system"), "light": self.t("light"), "dark": self.t("dark")
        }[self.config_data.appearance])
        appearance.pack(fill="x", pady=(5, 0))

        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)

        self.topbar = ctk.CTkFrame(self.content, height=72, corner_radius=0, fg_color=COLORS["surface"])
        self.topbar.grid(row=0, column=0, sticky="ew")
        self.topbar.grid_columnconfigure(0, weight=1)
        self.page_title = ctk.CTkLabel(
            self.topbar, text="", font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["text"], anchor="w",
        )
        self.page_title.grid(row=0, column=0, padx=28, pady=20, sticky="w")
        self.banner = ctk.CTkLabel(
            self.topbar, text=self.status_message, text_color=COLORS["muted"], anchor="e",
        )
        self.banner.grid(row=0, column=1, padx=28, pady=20, sticky="e")

        self.page_container = ctk.CTkFrame(self.content, fg_color="transparent")
        self.page_container.grid(row=1, column=0, sticky="nsew", padx=24, pady=20)
        self.page_container.grid_columnconfigure(0, weight=1)
        self.page_container.grid_rowconfigure(0, weight=1)

    def _show_page(self, page: str) -> None:
        self.current_page = page
        for key, button in self.nav_buttons.items():
            button.configure(
                fg_color="#2563EB" if key == page else "transparent",
                text_color="#FFFFFF" if key == page else "#CBD5E1",
            )
        self.page_title.configure(text=self.t(page))
        for child in self.page_container.winfo_children():
            child.destroy()
        builders = {
            "home": self._build_home,
            "server": self._build_server,
            "chatgpt": self._build_chatgpt,
            "logs": self._build_logs,
            "about": self._build_about,
        }
        builders[page]()

    def _scroll_page(self) -> ctk.CTkScrollableFrame:
        frame = ctk.CTkScrollableFrame(self.page_container, fg_color="transparent", corner_radius=0)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def _card(self, parent, title: str | None = None) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent, fg_color=COLORS["surface"], border_width=1,
            border_color=COLORS["border"], corner_radius=12,
        )
        card.grid_columnconfigure(0, weight=1)
        if title:
            ctk.CTkLabel(
                card, text=title, font=ctk.CTkFont(size=16, weight="bold"),
                text_color=COLORS["text"], anchor="w",
            ).grid(row=0, column=0, columnspan=4, padx=20, pady=(18, 12), sticky="ew")
        return card

    def _entry_row(self, parent, row: int, label: str, variable, *, browse: Callable | None = None, show: str | None = None):
        ctk.CTkLabel(parent, text=label, text_color=COLORS["text"], anchor="w").grid(
            row=row, column=0, padx=(20, 12), pady=8, sticky="w"
        )
        entry = ctk.CTkEntry(parent, textvariable=variable, show=show, height=36)
        entry.grid(row=row, column=1, columnspan=2 if browse is None else 1, padx=8, pady=8, sticky="ew")
        if browse is not None:
            ctk.CTkButton(parent, text=self.t("browse"), width=90, height=36, command=browse).grid(
                row=row, column=2, padx=(8, 20), pady=8
            )
        else:
            entry.grid_configure(padx=(8, 20))
        parent.grid_columnconfigure(1, weight=1)
        return entry

    def _build_home(self) -> None:
        page = self._scroll_page()

        repo_card = self._card(page, self.t("repository"))
        repo_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        repo_entry = self._entry_row(repo_card, 1, self.t("path"), self.repo_var, browse=self._browse_repo)
        repo_entry.configure(placeholder_text=self.t("repository_hint"))
        ctk.CTkButton(
            repo_card, text=self.t("open_folder"), fg_color="transparent",
            border_width=1, border_color=COLORS["border"], text_color=COLORS["text"],
            command=self._open_repo,
        ).grid(row=2, column=2, padx=(8, 20), pady=(4, 16), sticky="e")
        self.branch_label = ctk.CTkLabel(repo_card, text=f"{self.t('current_branch')}: {self._git_branch()}", text_color=COLORS["muted"])
        self.branch_label.grid(row=2, column=0, columnspan=2, padx=20, pady=(4, 16), sticky="w")

        mode_card = self._card(page, self.t("access_mode"))
        mode_card.grid(row=1, column=0, sticky="ew", pady=14)
        mode_values = [self.t("mode_read"), self.t("mode_write"), self.t("mode_test")]
        self.mode_segment = ctk.CTkSegmentedButton(
            mode_card, values=mode_values, height=38, command=self._mode_changed,
        )
        self.mode_segment.set({
            "read": self.t("mode_read"), "write": self.t("mode_write"), "test": self.t("mode_test")
        }[self.mode_var.get()])
        self.mode_segment.grid(row=1, column=0, columnspan=4, padx=20, pady=(2, 10), sticky="ew")
        self.mode_help = ctk.CTkLabel(mode_card, text="", text_color=COLORS["muted"], anchor="w", justify="left")
        self.mode_help.grid(row=2, column=0, columnspan=4, padx=20, pady=(0, 18), sticky="ew")
        self._update_mode_help()

        transport_card = self._card(page, self.t("transport"))
        transport_card.grid(row=2, column=0, sticky="ew", pady=14)
        transport_values = [self.t("stdio"), self.t("http")]
        self.transport_segment = ctk.CTkSegmentedButton(
            transport_card, values=transport_values, height=38, command=self._transport_changed,
        )
        self.transport_segment.set(self.t("stdio") if self.transport_var.get() == "stdio" else self.t("http"))
        self.transport_segment.grid(row=1, column=0, columnspan=4, padx=20, pady=(2, 10), sticky="ew")
        transport_desc = self.t("stdio_desc") if self.transport_var.get() == "stdio" else self.t("http_desc")
        ctk.CTkLabel(
            transport_card, text=transport_desc, text_color=COLORS["muted"], anchor="w", justify="left"
        ).grid(row=2, column=0, columnspan=4, padx=20, pady=(0, 12), sticky="ew")
        if self.transport_var.get() == "streamable-http":
            self._build_http_common(transport_card, start_row=3)

        advanced_button = ctk.CTkButton(
            page, text=("▾ " if self.advanced_open else "▸ ") + self.t("advanced"),
            fg_color="transparent", hover_color=COLORS["surface_alt"], text_color=COLORS["primary"],
            anchor="w", command=self._toggle_advanced,
        )
        advanced_button.grid(row=3, column=0, sticky="ew", pady=(8, 2))
        if self.advanced_open:
            advanced_card = self._card(page)
            advanced_card.grid(row=4, column=0, sticky="ew", pady=(2, 14))
            self._build_advanced(advanced_card)

        actions = ctk.CTkFrame(page, fg_color="transparent")
        actions.grid(row=5, column=0, sticky="ew", pady=(14, 26))
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            actions, text=self.t("save_restart") if self.processes.mcp.running else self.t("save"),
            height=42, command=self._save_action,
        ).grid(row=0, column=1, padx=6)
        if self.transport_var.get() == "streamable-http":
            if self.processes.mcp.running:
                ctk.CTkButton(
                    actions, text=self.t("stop_http"), height=42, fg_color=COLORS["danger"],
                    hover_color="#B91C1C", command=self._stop_http,
                ).grid(row=0, column=2, padx=6)
            else:
                ctk.CTkButton(
                    actions, text=self.t("start_http"), height=42, command=self._start_http,
                ).grid(row=0, column=2, padx=6)
        ctk.CTkButton(
            actions, text=self.t("run_test"), height=42, fg_color="transparent",
            border_width=1, border_color=COLORS["border"], text_color=COLORS["text"],
            command=self._run_smoke_test,
        ).grid(row=0, column=3, padx=(6, 0))

    def _build_http_common(self, card, start_row: int) -> None:
        ctk.CTkLabel(card, text=self.t("http_host"), text_color=COLORS["text"]).grid(
            row=start_row, column=0, padx=(20, 8), pady=8, sticky="w"
        )
        ctk.CTkEntry(card, textvariable=self.http_host_var, width=180).grid(
            row=start_row, column=1, padx=8, pady=8, sticky="ew"
        )
        ctk.CTkLabel(card, text=self.t("http_port"), text_color=COLORS["text"]).grid(
            row=start_row, column=2, padx=(18, 8), pady=8, sticky="w"
        )
        ctk.CTkEntry(card, textvariable=self.http_port_var, width=120).grid(
            row=start_row, column=3, padx=(8, 20), pady=8, sticky="ew"
        )
        ctk.CTkLabel(card, text=self.t("http_path"), text_color=COLORS["text"]).grid(
            row=start_row + 1, column=0, padx=(20, 8), pady=8, sticky="w"
        )
        ctk.CTkEntry(card, textvariable=self.http_path_var).grid(
            row=start_row + 1, column=1, padx=8, pady=8, sticky="ew"
        )
        ctk.CTkLabel(card, text=self.t("http_auth"), text_color=COLORS["text"]).grid(
            row=start_row + 1, column=2, padx=(18, 8), pady=8, sticky="w"
        )
        auth = ctk.CTkOptionMenu(
            card, values=[self.t("auth_none"), self.t("auth_bearer")], command=self._auth_changed,
        )
        auth.set(self.t("auth_bearer") if self.http_auth_var.get() == "bearer" else self.t("auth_none"))
        auth.grid(row=start_row + 1, column=3, padx=(8, 20), pady=8, sticky="ew")
        if self.http_auth_var.get() == "bearer":
            ctk.CTkLabel(card, text=self.t("http_token"), text_color=COLORS["text"]).grid(
                row=start_row + 2, column=0, padx=(20, 8), pady=8, sticky="w"
            )
            self.token_entry = ctk.CTkEntry(
                card, textvariable=self.http_token_var, show="" if self.http_token_visible else "•"
            )
            self.token_entry.grid(row=start_row + 2, column=1, columnspan=2, padx=8, pady=8, sticky="ew")
            token_actions = ctk.CTkFrame(card, fg_color="transparent")
            token_actions.grid(row=start_row + 2, column=3, padx=(8, 20), pady=8, sticky="e")
            ctk.CTkButton(
                token_actions, text=self.t("hide") if self.http_token_visible else self.t("show"),
                width=66, fg_color="transparent", border_width=1, border_color=COLORS["border"],
                text_color=COLORS["text"], command=self._toggle_http_token,
            ).pack(side="left", padx=(0, 5))
            ctk.CTkButton(
                token_actions, text=self.t("generate"), width=90, command=self._generate_http_token
            ).pack(side="left")
        endpoint = self._preview_endpoint()
        ctk.CTkLabel(card, text=f"{self.t('endpoint')}: {endpoint}", text_color=COLORS["primary"], anchor="w").grid(
            row=start_row + 3, column=0, columnspan=4, padx=20, pady=(8, 16), sticky="ew"
        )

    def _build_advanced(self, card) -> None:
        fields = [
            (self.t("max_file"), self.max_file_var),
            (self.t("max_patch"), self.max_patch_var),
            (self.t("max_search"), self.max_search_var),
            (self.t("max_output"), self.max_output_var),
            (self.t("test_timeout"), self.test_timeout_var),
        ]
        for index, (label, variable) in enumerate(fields):
            row = index // 2
            col = (index % 2) * 2
            ctk.CTkLabel(card, text=label, text_color=COLORS["text"], anchor="w").grid(
                row=row, column=col, padx=(20 if col == 0 else 18, 8), pady=9, sticky="w"
            )
            ctk.CTkEntry(card, textvariable=variable).grid(
                row=row, column=col + 1, padx=(8, 20), pady=9, sticky="ew"
            )
            card.grid_columnconfigure(col + 1, weight=1)
        ctk.CTkSwitch(card, text=self.t("dirty_worktree"), variable=self.dirty_var).grid(
            row=3, column=0, columnspan=2, padx=20, pady=10, sticky="w"
        )
        self._entry_row(card, 4, self.t("audit_log"), self.audit_var, browse=self._browse_audit)
        if self.transport_var.get() == "streamable-http":
            self._entry_row(card, 5, self.t("allowed_hosts"), self.allowed_hosts_var)
            self._entry_row(card, 6, self.t("allowed_origins"), self.allowed_origins_var)
            self._entry_row(card, 7, self.t("max_request"), self.max_request_var)
            ctk.CTkSwitch(card, text=self.t("json_response"), variable=self.json_response_var).grid(
                row=8, column=0, columnspan=2, padx=20, pady=10, sticky="w"
            )
            ctk.CTkSwitch(card, text=self.t("stateless"), variable=self.stateless_var).grid(
                row=8, column=2, columnspan=2, padx=20, pady=10, sticky="w"
            )

    def _build_server(self) -> None:
        page = self._scroll_page()
        status_card = self._card(page, self.t("mcp_process"))
        status_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.server_status_labels = {}
        rows = [
            (self.t("status"), self.t("running") if self.processes.mcp.running else self.t("stopped")),
            (self.t("transport_info"), self.t("stdio") if self.transport_var.get() == "stdio" else self.t("http")),
            (self.t("pid"), str(self.processes.mcp.pid or "-")),
            (self.t("uptime"), format_uptime(self.processes.mcp.uptime)),
        ]
        for index, (label, value) in enumerate(rows, start=1):
            ctk.CTkLabel(status_card, text=label, text_color=COLORS["muted"], anchor="w").grid(
                row=index, column=0, padx=20, pady=8, sticky="w"
            )
            widget = ctk.CTkLabel(status_card, text=value, text_color=COLORS["text"], anchor="e")
            widget.grid(row=index, column=1, padx=20, pady=8, sticky="e")
            self.server_status_labels[label] = widget
        note = self.t("stdio_note") if self.transport_var.get() == "stdio" else self.t("http_note")
        ctk.CTkLabel(status_card, text=note, text_color=COLORS["muted"], wraplength=760, justify="left").grid(
            row=5, column=0, columnspan=2, padx=20, pady=(12, 18), sticky="w"
        )
        buttons = ctk.CTkFrame(status_card, fg_color="transparent")
        buttons.grid(row=6, column=0, columnspan=2, padx=20, pady=(0, 18), sticky="e")
        if self.transport_var.get() == "streamable-http":
            ctk.CTkButton(
                buttons, text=self.t("stop_http") if self.processes.mcp.running else self.t("start_http"),
                fg_color=COLORS["danger"] if self.processes.mcp.running else COLORS["primary"],
                command=self._stop_http if self.processes.mcp.running else self._start_http,
            ).pack(side="left", padx=5)
        ctk.CTkButton(
            buttons, text=self.t("run_test"), fg_color="transparent", border_width=1,
            border_color=COLORS["border"], text_color=COLORS["text"], command=self._run_smoke_test,
        ).pack(side="left", padx=5)

        test_card = self._card(page, self.t("connection_test"))
        test_card.grid(row=1, column=0, sticky="ew", pady=14)
        desc = self.t("test_stdio") if self.transport_var.get() == "stdio" else self.t("test_http")
        ctk.CTkLabel(test_card, text=desc, text_color=COLORS["muted"], anchor="w", wraplength=760).grid(
            row=1, column=0, padx=20, pady=(0, 10), sticky="ew"
        )
        result_text = self.t("never") if not self.last_test else json.dumps(self.last_test, ensure_ascii=False, indent=2)
        self.test_textbox = ctk.CTkTextbox(test_card, height=145)
        self.test_textbox.grid(row=2, column=0, padx=20, pady=(0, 18), sticky="ew")
        self.test_textbox.insert("1.0", result_text)
        self.test_textbox.configure(state="disabled")

        config_card = self._card(page, self.t("client_config"))
        config_card.grid(row=2, column=0, sticky="ew", pady=14)
        snippet = self._client_config_text()
        self.client_config_box = ctk.CTkTextbox(config_card, height=190)
        self.client_config_box.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.client_config_box.insert("1.0", snippet)
        self.client_config_box.configure(state="disabled")
        ctk.CTkButton(
            config_card, text=self.t("copy_client_config"), command=lambda: self._copy(snippet)
        ).grid(row=2, column=0, padx=20, pady=(0, 18), sticky="e")

    def _build_chatgpt(self) -> None:
        page = self._scroll_page()
        intro = self._card(page, self.t("chatgpt"))
        intro.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        ctk.CTkLabel(
            intro, text=self.t("chatgpt_intro"), text_color=COLORS["muted"],
            wraplength=800, justify="left", anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 18), sticky="ew")

        form = self._card(page, self.t("chatgpt"))
        form.grid(row=1, column=0, sticky="ew", pady=14)
        self._entry_row(form, 1, self.t("tunnel_client"), self.tunnel_path_var, browse=self._browse_tunnel)
        self._entry_row(form, 2, self.t("tunnel_id"), self.tunnel_id_var)
        self._entry_row(form, 3, self.t("profile"), self.tunnel_profile_var)
        ctk.CTkLabel(form, text=self.t("api_key"), text_color=COLORS["text"], anchor="w").grid(
            row=4, column=0, padx=(20, 12), pady=8, sticky="w"
        )
        self.api_key_entry = ctk.CTkEntry(
            form, textvariable=self.api_key_var, show="" if self.api_key_visible else "•"
        )
        self.api_key_entry.grid(row=4, column=1, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(
            form, text=self.t("hide") if self.api_key_visible else self.t("show"), width=90,
            fg_color="transparent", border_width=1, border_color=COLORS["border"],
            text_color=COLORS["text"], command=self._toggle_api_key,
        ).grid(row=4, column=2, padx=(8, 20), pady=8)
        form.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(form, text=self.t("api_key_not_saved"), text_color=COLORS["warning"], anchor="w").grid(
            row=5, column=0, columnspan=3, padx=20, pady=(2, 10), sticky="ew"
        )
        if self.transport_var.get() == "streamable-http" and self.http_auth_var.get() == "bearer":
            ctk.CTkLabel(
                form, text=self.t("http_tunnel_auth_warning"), text_color=COLORS["warning"],
                wraplength=760, justify="left",
            ).grid(row=6, column=0, columnspan=3, padx=20, pady=(0, 12), sticky="ew")
        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.grid(row=7, column=0, columnspan=3, padx=20, pady=(8, 18), sticky="e")
        for label, command in (
            (self.t("detect"), self._detect_tunnel),
            (self.t("initialize"), self._init_tunnel),
            (self.t("doctor"), self._doctor_tunnel),
        ):
            ctk.CTkButton(
                actions, text=label, fg_color="transparent", border_width=1,
                border_color=COLORS["border"], text_color=COLORS["text"], command=command,
            ).pack(side="left", padx=4)
        ctk.CTkButton(
            actions,
            text=self.t("stop_tunnel") if self.processes.tunnel.running else self.t("start_tunnel"),
            fg_color=COLORS["danger"] if self.processes.tunnel.running else COLORS["primary"],
            command=self._stop_tunnel if self.processes.tunnel.running else self._start_tunnel,
        ).pack(side="left", padx=4)

        status = self._card(page, self.t("tunnel_status"))
        status.grid(row=2, column=0, sticky="ew", pady=14)
        values = [
            (self.t("status"), self.t("running") if self.processes.tunnel.running else self.t("stopped")),
            (self.t("pid"), str(self.processes.tunnel.pid or "-")),
            (self.t("profile"), self.tunnel_profile_var.get() or "-"),
            (self.t("transport_info"), self.t("stdio") if self.transport_var.get() == "stdio" else self.t("http")),
        ]
        for index, (label, value) in enumerate(values, start=1):
            ctk.CTkLabel(status, text=label, text_color=COLORS["muted"]).grid(
                row=index, column=0, padx=20, pady=8, sticky="w"
            )
            ctk.CTkLabel(status, text=value, text_color=COLORS["text"]).grid(
                row=index, column=1, padx=20, pady=8, sticky="e"
            )

    def _build_logs(self) -> None:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        tabs = ctk.CTkTabview(page, fg_color=COLORS["surface"])
        tabs.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.log_boxes = {}
        for key in ("log_mcp", "log_tunnel", "log_audit"):
            name = self.t(key)
            tab = tabs.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            box = ctk.CTkTextbox(tab, font=("Consolas" if os.name == "nt" else "monospace", 12))
            box.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
            self.log_boxes[key] = box
        controls = ctk.CTkFrame(page, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="e", pady=(10, 0))
        ctk.CTkButton(
            controls, text=self.t("refresh"), command=self._refresh_logs_now
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            controls, text=self.t("clear_view"), fg_color="transparent", border_width=1,
            border_color=COLORS["border"], text_color=COLORS["text"], command=self._clear_log_view,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            controls, text=self.t("export"), fg_color="transparent", border_width=1,
            border_color=COLORS["border"], text_color=COLORS["text"], command=self._export_logs,
        ).pack(side="left", padx=4)
        self._refresh_logs_now()

    def _build_about(self) -> None:
        page = self._scroll_page()
        card = self._card(page)
        card.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            card, text="Local Repo MCP", font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, padx=28, pady=(30, 8), sticky="w")
        ctk.CTkLabel(
            card, text=self.t("about_title"), font=ctk.CTkFont(size=17), text_color=COLORS["primary"]
        ).grid(row=1, column=0, padx=28, pady=4, sticky="w")
        ctk.CTkLabel(
            card, text=self.t("about_desc"), text_color=COLORS["muted"], wraplength=780, justify="left"
        ).grid(row=2, column=0, padx=28, pady=(4, 20), sticky="w")
        ctk.CTkLabel(card, text=f"{self.t('version')}: {VERSION}", text_color=COLORS["text"]).grid(
            row=3, column=0, padx=28, pady=6, sticky="w"
        )
        ctk.CTkLabel(
            card, text=self.t("security_boundary"), font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=4, column=0, padx=28, pady=(22, 8), sticky="w")
        ctk.CTkLabel(
            card, text="✓ " + self.t("boundary_items").replace("\n", "\n✓ "),
            text_color=COLORS["muted"], justify="left",
        ).grid(row=5, column=0, padx=28, pady=(0, 24), sticky="w")
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=6, column=0, padx=28, pady=(0, 30), sticky="w")
        ctk.CTkButton(actions, text=self.t("github"), command=lambda: webbrowser.open(GITHUB_URL)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            actions, text=self.t("documentation"), fg_color="transparent", border_width=1,
            border_color=COLORS["border"], text_color=COLORS["text"], command=self._open_docs,
        ).pack(side="left")

    def _collect_config(self) -> AppConfig | None:
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
                http_auth_mode=self.http_auth_var.get(),
                http_allowed_hosts=self.allowed_hosts_var.get().strip(),
                http_allowed_origins=self.allowed_origins_var.get().strip(),
                http_json_response=self.json_response_var.get(),
                http_stateless=self.stateless_var.get(),
                http_max_request_bytes=int(self.max_request_var.get()) * 1024,
                max_file_bytes=int(self.max_file_var.get()) * 1000,
                max_patch_bytes=int(self.max_patch_var.get()) * 1000,
                max_search_results=int(self.max_search_var.get()),
                max_output_bytes=int(self.max_output_var.get()) * 1000,
                allow_dirty_worktree=self.dirty_var.get(),
                audit_log=self.audit_var.get().strip(),
                test_timeout_max=int(self.test_timeout_var.get()),
                tunnel_client_path=self.tunnel_path_var.get().strip() or "tunnel-client",
                tunnel_id=self.tunnel_id_var.get().strip(),
                tunnel_profile=self.tunnel_profile_var.get().strip() or "local-repo",
                control_plane_api_key=self.api_key_var.get().strip(),
                http_auth_token=self.http_token_var.get().strip(),
            )
        except ValueError:
            messagebox.showerror(self.t("error"), self.t("max_file_invalid"))
            return None
        if cfg.http_auth_mode == "bearer" and not cfg.http_auth_token:
            cfg.ensure_http_token()
            self.http_token_var.set(cfg.http_auth_token)
        errors = cfg.validate()
        if errors:
            message = "\n".join(f"• {self.t(key)}" for key in errors)
            messagebox.showerror(self.t("error"), message)
            return None
        return cfg

    def _save(self) -> AppConfig | None:
        cfg = self._collect_config()
        if cfg is None:
            return None
        save_config(cfg)
        self.config_data = cfg
        self._set_status(self.t("saved"), COLORS["success"])
        return cfg

    def _save_action(self) -> None:
        was_running = self.processes.mcp.running
        cfg = self._save()
        if cfg is None:
            return
        if was_running:
            self._run_background(lambda: self.processes.restart_http(cfg), self.t("saved"), rebuild=True)

    def _start_http(self) -> None:
        cfg = self._save()
        if cfg is None:
            return
        if cfg.transport != "streamable-http":
            return
        self._run_background(lambda: self.processes.start_http(cfg), self.t("running"), rebuild=True)

    def _stop_http(self) -> None:
        self._run_background(self.processes.mcp.stop, self.t("stopped"), rebuild=True)

    def _run_smoke_test(self) -> None:
        cfg = self._save()
        if cfg is None:
            return
        if cfg.transport == "streamable-http" and not self.processes.mcp.running:
            messagebox.showerror(self.t("error"), self.t("start_http"))
            return

        def task():
            return run_smoke_test(cfg)

        def success(result):
            self.last_test = result
            self._set_status(self.t("test_success"), COLORS["success"])
            if self.current_page == "server":
                self._show_page("server")

        self._run_background(task, on_success=success)

    def _detect_tunnel(self) -> None:
        cfg = self._collect_config()
        if cfg:
            self._run_background(lambda: self.tunnel.version(cfg), on_success=lambda value: self._set_status(value, COLORS["success"]))

    def _init_tunnel(self) -> None:
        cfg = self._save()
        if cfg:
            self._run_background(lambda: self.tunnel.init_profile(cfg), on_success=lambda value: self._show_result(value))

    def _doctor_tunnel(self) -> None:
        cfg = self._collect_config()
        if cfg:
            self._run_background(lambda: self.tunnel.doctor(cfg), on_success=lambda value: self._show_result(value))

    def _start_tunnel(self) -> None:
        cfg = self._save()
        if cfg:
            self._run_background(lambda: self.tunnel.start(cfg), self.t("running"), rebuild=True)

    def _stop_tunnel(self) -> None:
        self._run_background(self.processes.tunnel.stop, self.t("stopped"), rebuild=True)

    def _run_background(self, task: Callable, success_message: str | None = None, *, on_success: Callable | None = None, rebuild: bool = False) -> None:
        if self.busy:
            self._set_status(self.t("busy"), COLORS["warning"])
            return
        self.busy = True
        self._set_status(self.t("starting"), COLORS["primary"])

        def worker():
            try:
                result = task()
            except Exception as exc:  # GUI boundary: show actionable error
                self.after(0, lambda: self._operation_failed(str(exc)))
                return
            self.after(0, lambda: self._operation_succeeded(result, success_message, on_success, rebuild))

        threading.Thread(target=worker, daemon=True).start()

    def _operation_failed(self, error: str) -> None:
        self.busy = False
        self._set_status(error, COLORS["danger"])
        messagebox.showerror(self.t("error"), error)

    def _operation_succeeded(self, result, message: str | None, callback: Callable | None, rebuild: bool) -> None:
        self.busy = False
        if callback:
            callback(result)
        elif message:
            self._set_status(message, COLORS["success"])
        else:
            self._set_status(self.t("ready"), COLORS["success"])
        if rebuild:
            self._show_page(self.current_page)

    def _show_result(self, value: str) -> None:
        self._set_status(self.t("result_ok"), COLORS["success"])
        messagebox.showinfo(self.t("result_ok"), value)

    def _set_status(self, text: str, color=None) -> None:
        self.status_message = text
        if hasattr(self, "banner"):
            self.banner.configure(text=text, text_color=color or COLORS["muted"])

    def _mode_changed(self, value: str) -> None:
        mapping = {self.t("mode_read"): "read", self.t("mode_write"): "write", self.t("mode_test"): "test"}
        self.mode_var.set(mapping[value])
        self._update_mode_help()

    def _update_mode_help(self) -> None:
        if not hasattr(self, "mode_help"):
            return
        mapping = {
            "read": self.t("mode_read_desc"),
            "write": self.t("mode_write_desc") + "\n⚠ " + self.t("write_warning"),
            "test": self.t("mode_test_desc") + "\n⚠ " + self.t("test_warning"),
        }
        self.mode_help.configure(text=mapping[self.mode_var.get()])

    def _transport_changed(self, value: str) -> None:
        selected = "stdio" if value == self.t("stdio") else "streamable-http"
        if self.processes.mcp.running and selected != self.transport_var.get():
            messagebox.showwarning(self.t("warning"), self.t("stop_http"))
            self.transport_segment.set(self.t("http"))
            return
        self.transport_var.set(selected)
        self._show_page("home")

    def _auth_changed(self, value: str) -> None:
        self.http_auth_var.set("bearer" if value == self.t("auth_bearer") else "none")
        if self.http_auth_var.get() == "bearer" and not self.http_token_var.get():
            self._generate_http_token(rebuild=False)
        self._show_page("home")

    def _toggle_http_token(self) -> None:
        self.http_token_visible = not self.http_token_visible
        self._show_page("home")

    def _toggle_api_key(self) -> None:
        self.api_key_visible = not self.api_key_visible
        self._show_page("chatgpt")

    def _generate_http_token(self, rebuild: bool = True) -> None:
        import secrets
        self.http_token_var.set(secrets.token_urlsafe(32))
        if rebuild:
            self._show_page("home")

    def _toggle_advanced(self) -> None:
        self.advanced_open = not self.advanced_open
        self._show_page("home")

    def _change_language(self, value: str) -> None:
        language = "zh" if value == "中文" else "en"
        cfg = self._collect_config_quiet() or self.config_data
        cfg.language = language
        cfg.control_plane_api_key = self.api_key_var.get().strip()
        cfg.http_auth_token = self.http_token_var.get().strip()
        save_config(cfg)
        self.config_data = cfg
        self._build_shell()
        self._show_page(self.current_page)

    def _change_appearance(self, value: str) -> None:
        reverse = {self.t("system"): "system", self.t("light"): "light", self.t("dark"): "dark"}
        selected = reverse[value]
        cfg = self._collect_config_quiet() or self.config_data
        cfg.appearance = selected
        cfg.control_plane_api_key = self.api_key_var.get().strip()
        cfg.http_auth_token = self.http_token_var.get().strip()
        save_config(cfg)
        self.config_data = cfg
        ctk.set_appearance_mode(selected)

    def _browse_repo(self) -> None:
        path = filedialog.askdirectory(initialdir=self.repo_var.get() or str(Path.home()))
        if path:
            self.repo_var.set(path)
            if hasattr(self, "branch_label"):
                self.branch_label.configure(text=f"{self.t('current_branch')}: {self._git_branch()}")

    def _browse_audit(self) -> None:
        path = filedialog.asksaveasfilename(
            initialfile="audit.jsonl", defaultextension=".jsonl",
            filetypes=[("JSON Lines", "*.jsonl"), ("All files", "*")],
        )
        if path:
            self.audit_var.set(path)

    def _browse_tunnel(self) -> None:
        path = filedialog.askopenfilename()
        if path:
            self.tunnel_path_var.set(path)

    def _open_repo(self) -> None:
        path = Path(self.repo_var.get()).expanduser()
        if not path.exists():
            return
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _git_branch(self) -> str:
        repo = self.repo_var.get().strip()
        if not repo:
            return "-"
        try:
            result = subprocess.run(
                ["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"],
                text=True, capture_output=True, timeout=5, check=False, shell=False,
            )
            if result.returncode != 0:
                return self.t("git_unavailable")
            value = result.stdout.strip()
            return self.t("detached_head") if value == "HEAD" else value
        except (OSError, subprocess.SubprocessError):
            return self.t("git_unavailable")

    def _preview_endpoint(self) -> str:
        try:
            port = int(self.http_port_var.get())
        except ValueError:
            port = 8000
        host = self.http_host_var.get().strip() or "127.0.0.1"
        if host == "0.0.0.0":
            host = "127.0.0.1"
        elif host == "::":
            host = "::1"
        display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
        path = self.http_path_var.get().strip() or "/mcp"
        if not path.startswith("/"):
            path = "/" + path
        return f"http://{display_host}:{port}{path}"

    def _client_config_text(self) -> str:
        cfg = self._collect_config_quiet()
        if cfg is None:
            return ""
        if cfg.transport == "streamable-http":
            payload: dict = {"url": cfg.endpoint_url(), "transport": "streamable-http"}
            if cfg.http_auth_mode == "bearer":
                payload["headers"] = {"Authorization": "Bearer <LOCAL_REPO_MCP_TOKEN>"}
            return json.dumps({"mcpServers": {"local-repo": payload}}, indent=2)
        env = cfg.mcp_env()
        env["MCP_TRANSPORT"] = "stdio"
        env.pop("HTTP_AUTH_TOKEN", None)
        return json.dumps({
            "mcpServers": {
                "local-repo": {
                    "command": sys.executable,
                    "args": [str(ROOT / "server.py")],
                    "env": env,
                }
            }
        }, indent=2)

    def _collect_config_quiet(self) -> AppConfig | None:
        try:
            return AppConfig(
                language=self.config_data.language,
                appearance=self.config_data.appearance,
                repo_root=self.repo_var.get().strip(), mcp_mode=self.mode_var.get(),
                transport=self.transport_var.get(), http_host=self.http_host_var.get().strip() or "127.0.0.1",
                http_port=int(self.http_port_var.get()), http_path=self.http_path_var.get().strip() or "/mcp",
                http_auth_mode=self.http_auth_var.get(), http_auth_token=self.http_token_var.get().strip(),
                http_allowed_hosts=self.allowed_hosts_var.get().strip(), http_allowed_origins=self.allowed_origins_var.get().strip(),
                http_json_response=self.json_response_var.get(), http_stateless=self.stateless_var.get(),
                http_max_request_bytes=int(self.max_request_var.get()) * 1024,
                max_file_bytes=int(self.max_file_var.get()) * 1000, max_patch_bytes=int(self.max_patch_var.get()) * 1000,
                max_search_results=int(self.max_search_var.get()), max_output_bytes=int(self.max_output_var.get()) * 1000,
                allow_dirty_worktree=self.dirty_var.get(), audit_log=self.audit_var.get().strip(),
                test_timeout_max=int(self.test_timeout_var.get()), tunnel_client_path=self.tunnel_path_var.get().strip(),
                tunnel_id=self.tunnel_id_var.get().strip(), tunnel_profile=self.tunnel_profile_var.get().strip(),
                control_plane_api_key=self.api_key_var.get().strip(),
            )
        except ValueError:
            return None

    def _copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status(self.t("copied"), COLORS["success"])

    def _open_docs(self) -> None:
        filename = "README.zh-CN.md" if self.config_data.language == "zh" else "README.md"
        path = ROOT / filename
        if path.exists():
            webbrowser.open(path.as_uri())
        else:
            webbrowser.open(GITHUB_URL)

    def _refresh_logs_now(self) -> None:
        if not hasattr(self, "log_boxes"):
            return
        contents = {
            "log_mcp": "\n".join(self.processes.mcp.snapshot()),
            "log_tunnel": "\n".join(self.processes.tunnel.snapshot()),
            "log_audit": self._tail_audit(),
        }
        for key, box in self.log_boxes.items():
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("1.0", contents.get(key, ""))
            box.see("end")
            box.configure(state="disabled")

    def _tail_audit(self, limit: int = 500) -> str:
        path_text = self.audit_var.get().strip()
        if not path_text:
            return ""
        path = Path(path_text).expanduser()
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(lines[-limit:])
        except (FileNotFoundError, OSError):
            return ""

    def _clear_log_view(self) -> None:
        for box in getattr(self, "log_boxes", {}).values():
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.configure(state="disabled")

    def _export_logs(self) -> None:
        path = filedialog.asksaveasfilename(initialfile="local-repo-mcp-logs.txt", defaultextension=".txt")
        if not path:
            return
        text = "\n\n===== MCP =====\n" + "\n".join(self.processes.mcp.snapshot())
        text += "\n\n===== TUNNEL =====\n" + "\n".join(self.processes.tunnel.snapshot())
        text += "\n\n===== AUDIT =====\n" + self._tail_audit()
        Path(path).write_text(text, encoding="utf-8")

    def _periodic_refresh(self) -> None:
        if self.current_page == "logs":
            self._refresh_logs_now()
        if self.current_page == "server" and hasattr(self, "server_status_labels"):
            status_key = self.t("status")
            pid_key = self.t("pid")
            uptime_key = self.t("uptime")
            if status_key in self.server_status_labels:
                self.server_status_labels[status_key].configure(
                    text=self.t("running") if self.processes.mcp.running else self.t("stopped")
                )
            if pid_key in self.server_status_labels:
                self.server_status_labels[pid_key].configure(text=str(self.processes.mcp.pid or "-"))
            if uptime_key in self.server_status_labels:
                self.server_status_labels[uptime_key].configure(text=format_uptime(self.processes.mcp.uptime))
        self.after(1000, self._periodic_refresh)

    def _on_close(self) -> None:
        if self.processes.mcp.running or self.processes.tunnel.running:
            if not messagebox.askyesno(self.t("confirm"), self.t("exit_confirm")):
                return
        self.processes.stop_all()
        self.destroy()


def main() -> None:
    app = LocalRepoMCPApp()
    app.mainloop()


if __name__ == "__main__":
    main()
