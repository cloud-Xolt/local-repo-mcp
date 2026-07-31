"""Local Repo MCP GUI — 简版设计稿布局还原。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from gui.config import MCP_MODES, AppConfig, PROJECT_ROOT, load_config, reset_defaults, save_all
from gui.i18n import Lang, bind, t
from gui.process_manager import ProcessManager
from gui.theme import CARD_RADIUS, BTN_HEIGHT, CONTENT_PADX, CONTENT_PADY, DARK, FORM_COL_GAP, INFO_PANEL_WIDTH, INPUT_HEIGHT, LIGHT, SIDEBAR_WIDTH, TYPO, Theme
from gui.widgets import ChecklistRow, FeatureCard, FormField, InfoRow, PageHeader, SectionHeader, font

DEFAULT_READ_DENY_PATTERNS = (
    ".git/**",
    ".env",
    ".env.*",
    "**/.env",
    "*.pem",
    "*.key",
    ".ssh/**",
    "**/credentials/**",
    "**/secrets/**",
    "*id_rsa*",
    ".github/workflows/**",
)

VERSION = "1.0.0"
NAV: list[tuple[str, str]] = [
    ("general", "nav_general"),
    ("repo", "nav_repo"),
    ("security", "nav_security"),
    ("mcp", "nav_mcp"),
    ("test", "nav_test"),
    ("logs", "nav_logs"),
    ("about", "nav_about"),
]


def git_branch(repo_root: str, git_exe: str = "git") -> str:
    if not repo_root or not Path(repo_root).exists():
        return "main"
    try:
        r = subprocess.run(
            [git_exe, "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return r.stdout.strip() or "main"
    except Exception:
        return "main"


def start_command_text() -> str:
    py = PROJECT_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not py.exists():
        py = Path(sys.executable)
    launcher = (PROJECT_ROOT / "launch_mcp.py").resolve()
    return f'"{py}" "{launcher}"'


class MCPControlApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.lang: Lang = "zh"
        self.theme = LIGHT
        self._ = bind(self.lang)
        self.config_data = load_config()
        self.process_manager = ProcessManager(on_log=self._on_log)
        self._busy = False
        self._audit_offset = 0
        self._page = "general"
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        self._selected_mode = self.config_data.mcp_mode
        self._advanced_open = False
        self._last_scan = "-"
        self._issues = 0

        self.title("Local Repo MCP")
        self.geometry("1320x880")
        self.minsize(900, 620)
        self.configure(fg_color=self.theme.bg_app)

        self._build()
        self._load()
        self._show("general")
        self._tick()
        if self.config_data.auto_start_mcp:
            self.after(600, self._start_mcp)

    # ── layout ─────────────────────────────────────────────

    def _build(self) -> None:
        th = self.theme
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # sidebar
        sb = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, corner_radius=0, fg_color=th.bg_sidebar, border_width=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        self._sidebar = sb

        brand = ctk.CTkFrame(sb, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(24, 20))
        ctk.CTkLabel(brand, text="📦", font=font(22)).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(brand, text="Local Repo MCP", font=font(TYPO.brand, "bold"), text_color=th.text_title).pack(side="left")

        nav = ctk.CTkFrame(sb, fg_color="transparent")
        nav.pack(fill="both", expand=True, padx=12)
        for key, lk in NAV:
            btn = ctk.CTkButton(
                nav,
                text=f"  {t(lk, self.lang)}",
                anchor="w",
                height=42,
                corner_radius=10,
                fg_color="transparent",
                text_color=th.text,
                hover_color=th.bg_nav_active,
                font=font(TYPO.nav),
                command=lambda k=key: self._show(k),
            )
            btn.pack(fill="x", pady=2)
            self._nav_btns[key] = btn

        foot = ctk.CTkFrame(sb, fg_color="transparent")
        foot.pack(fill="x", padx=20, pady=18)
        row = ctk.CTkFrame(foot, fg_color="transparent")
        row.pack(fill="x")
        self._sb_dot = ctk.CTkLabel(row, text="●", font=font(13), text_color=th.text_muted)
        self._sb_dot.pack(side="left")
        self._sb_status = ctk.CTkLabel(row, text="", font=font(12), text_color=th.text_muted)
        self._sb_status.pack(side="left", padx=4)
        ctk.CTkLabel(foot, text=f"{t('version', self.lang)}: {VERSION}", font=font(12), text_color=th.text_muted).pack(
            anchor="w", pady=(6, 0)
        )

        # main
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)
        self._main = main

        hdr = ctk.CTkFrame(main, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=CONTENT_PADX, pady=(20, 0))
        self._lang_zh = ctk.CTkButton(
            hdr, text="中文", width=48, height=30, fg_color="transparent",
            text_color=th.header_btn_active, font=font(TYPO.body), command=lambda: self._lang("zh"),
        )
        self._lang_zh.pack(side="right")
        self._lang_en = ctk.CTkButton(
            hdr, text="EN", width=40, height=30, fg_color="transparent",
            text_color=th.header_btn, font=font(TYPO.body), command=lambda: self._lang("en"),
        )
        self._lang_en.pack(side="right", padx=(0, 8))
        self._theme_btn = ctk.CTkButton(
            hdr, text="☀", width=36, height=30, fg_color=th.bg_card,
            border_width=1, border_color=th.border, font=font(16), command=self._toggle_theme,
        )
        self._theme_btn.pack(side="right", padx=(0, 12))

        host = ctk.CTkFrame(main, fg_color="transparent")
        host.grid(row=1, column=0, sticky="nsew", padx=CONTENT_PADX, pady=(12, CONTENT_PADY))
        host.grid_columnconfigure(0, weight=1)
        host.grid_rowconfigure(0, weight=1)
        self._pages: dict[str, ctk.CTkFrame] = {}
        for key, _ in NAV:
            p = ctk.CTkFrame(host, fg_color="transparent")
            p.grid(row=0, column=0, sticky="nsew")
            self._pages[key] = p
            p.grid_remove()

        self._page_general()
        self._page_repo()
        self._page_security()
        self._page_mcp()
        self._page_test()
        self._page_logs()
        self._page_about()

    def _card(self, parent, **kw) -> ctk.CTkScrollableFrame:
        th = self.theme
        defaults = dict(fg_color=th.bg_card, corner_radius=16, border_width=1, border_color=th.border)
        defaults.update(kw)
        return ctk.CTkScrollableFrame(parent, **defaults)

    def _page_header(self, parent, title_k: str, sub_k: str) -> PageHeader:
        hdr = PageHeader(parent, self.theme)
        hdr.set(t(title_k, self.lang), t(sub_k, self.lang))
        hdr.pack(anchor="w", fill="x", pady=(0, 20))
        return hdr

    # ── General ──────────────────────────────────────────

    def _page_general(self) -> None:
        page = self._pages["general"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        page.grid_rowconfigure(2, weight=0)
        page.grid_rowconfigure(3, weight=0)
        th = self.theme

        self._general_header = PageHeader(page, th)
        self._general_header.set(t("general_title", self.lang), t("general_sub", self.lang))
        self._general_header.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        split = ctk.CTkFrame(page, fg_color="transparent")
        split.grid(row=1, column=0, sticky="nsew")
        split.grid_columnconfigure(0, weight=1)
        split.grid_columnconfigure(1, weight=0, minsize=INFO_PANEL_WIDTH)
        split.grid_rowconfigure(0, weight=1)

        left_shell = ctk.CTkFrame(
            split, fg_color=th.bg_card, corner_radius=CARD_RADIUS,
            border_width=1, border_color=th.border,
        )
        left_shell.grid(row=0, column=0, sticky="nsew", padx=(0, FORM_COL_GAP))
        left_shell.grid_rowconfigure(0, weight=1)
        left_shell.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkScrollableFrame(
            left_shell,
            fg_color=th.bg_card,
            corner_radius=0,
            border_width=0,
            scrollbar_button_color=th.border,
            scrollbar_button_hover_color=th.text_muted,
        )
        inner.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        inner.grid_columnconfigure(0, weight=1)

        form = ctk.CTkFrame(inner, fg_color="transparent")
        form.pack(fill="x", padx=24, pady=24)
        form.grid_columnconfigure(0, weight=1)

        SectionHeader(form, th, t("repo_settings", self.lang)).pack(anchor="w", pady=(0, 16))

        pr = ctk.CTkFrame(form, fg_color="transparent")
        pr.pack(fill="x")
        pr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            pr, text=f"{t('repo_path', self.lang)} *", font=font(TYPO.label, "bold"),
            text_color=th.text_title, anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        self._repo_path = ctk.CTkEntry(
            pr, height=INPUT_HEIGHT, font=font(TYPO.body),
            fg_color=th.bg_input, border_color=th.border, corner_radius=8,
        )
        self._repo_path.grid(row=1, column=0, sticky="ew", pady=(8, 0), padx=(0, 10))
        ctk.CTkButton(
            pr, text=f"📁 {t('select', self.lang)}", width=96, height=INPUT_HEIGHT,
            fg_color=th.bg_card, border_width=1, border_color=th.border,
            font=font(TYPO.body), command=self._browse_repo,
        ).grid(row=1, column=1)
        ctk.CTkLabel(
            pr, text=t("repo_path_hint", self.lang), font=font(TYPO.hint),
            text_color=th.text_hint, anchor="w",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 20))

        self._branch_field = FormField(form, th, t("repo_branch", self.lang), hint=t("branch_hint", self.lang))
        self._branch_field.pack(fill="x", pady=(0, 24))

        SectionHeader(form, th, t("service_settings", self.lang)).pack(anchor="w", pady=(0, 16))

        self._service_port = FormField(
            form, th, t("service_port", self.lang), required=True, hint=t("service_port_hint", self.lang),
        )
        self._service_port.pack(fill="x", pady=(0, 16))

        mode_wrap = ctk.CTkFrame(form, fg_color="transparent")
        mode_wrap.pack(fill="x", pady=(0, 4))
        mode_wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            mode_wrap, text=t("service_mode", self.lang), font=font(TYPO.label, "bold"),
            text_color=th.text_title, anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self._service_mode = ctk.CTkComboBox(
            mode_wrap,
            values=[t("service_mode_stdio", self.lang)],
            height=INPUT_HEIGHT,
            font=font(TYPO.body),
            state="readonly",
            corner_radius=8,
        )
        self._service_mode.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self._service_mode.set(t("service_mode_stdio", self.lang))
        ctk.CTkLabel(
            mode_wrap, text=t("service_mode_hint", self.lang), font=font(TYPO.hint),
            text_color=th.text_hint, anchor="w",
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))

        right = ctk.CTkFrame(
            split, fg_color=th.bg_card, corner_radius=CARD_RADIUS,
            border_width=1, border_color=th.border, width=INFO_PANEL_WIDTH,
        )
        right.grid(row=0, column=1, sticky="nsew")
        rh = ctk.CTkFrame(right, fg_color="transparent")
        rh.pack(fill="x", padx=24, pady=(24, 16))
        ctk.CTkLabel(rh, text=t("service_info", self.lang), font=font(TYPO.section, "bold"), text_color=th.text_title).pack(side="left")
        self._run_badge = ctk.CTkLabel(
            rh, text=t("stopped", self.lang), font=font(TYPO.badge),
            text_color=th.success, fg_color=th.success_bg, corner_radius=12, width=76, height=28,
        )
        self._run_badge.pack(side="right")

        info = ctk.CTkFrame(right, fg_color="transparent")
        info.pack(fill="x", padx=24, pady=(0, 8))
        self._pi_mcp = InfoRow(info, th, t("mcp_service", self.lang))
        self._pi_mcp.pack(fill="x", pady=8)
        self._pi_port = InfoRow(info, th, t("port", self.lang))
        self._pi_port.pack(fill="x", pady=8)
        self._pi_repo = InfoRow(info, th, t("repo_name", self.lang))
        self._pi_repo.pack(fill="x", pady=8)
        self._pi_branch = InfoRow(info, th, t("branch", self.lang))
        self._pi_branch.pack(fill="x", pady=8)

        bf = ctk.CTkFrame(right, fg_color="transparent")
        bf.pack(fill="x", padx=24, pady=(24, 24))
        ctk.CTkButton(
            bf, text=f"✓  {t('save_apply', self.lang)}", height=BTN_HEIGHT,
            font=font(TYPO.body, "bold"), fg_color=th.accent, hover_color=th.accent_hover,
            command=self._save_and_apply,
        ).pack(fill="x", pady=(0, 10))
        ctk.CTkButton(
            bf, text=f"📶  {t('test_connection', self.lang)}", height=BTN_HEIGHT,
            font=font(TYPO.body), fg_color=th.bg_app, border_width=1, border_color=th.border,
            text_color=th.text, command=self._go_test,
        ).pack(fill="x")

        adv_bar = ctk.CTkFrame(page, fg_color=th.bg_card, corner_radius=CARD_RADIUS, border_width=1, border_color=th.border)
        adv_bar.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        adv_head = ctk.CTkFrame(adv_bar, fg_color="transparent", cursor="hand2")
        adv_head.pack(fill="x", padx=20, pady=14)
        self._adv_head = adv_head
        adv_head.bind("<Button-1>", lambda _e: self._toggle_advanced())
        ctk.CTkLabel(adv_head, text="⚙", font=font(16), text_color=th.text_muted, cursor="hand2").pack(side="left")
        title_lbl = ctk.CTkLabel(
            adv_head, text=t("advanced_config", self.lang), font=font(TYPO.body, "bold"),
            text_color=th.text_title, cursor="hand2",
        )
        title_lbl.pack(side="left", padx=(8, 12))
        title_lbl.bind("<Button-1>", lambda _e: self._toggle_advanced())
        self._adv_hint = ctk.CTkLabel(
            adv_head, text=t("advanced_hint", self.lang), font=font(TYPO.hint),
            text_color=th.text_hint, cursor="hand2",
        )
        self._adv_hint.pack(side="left")
        self._adv_hint.bind("<Button-1>", lambda _e: self._toggle_advanced())
        self._adv_chevron = ctk.CTkLabel(adv_head, text="▼", font=font(12), text_color=th.text_muted, width=20, cursor="hand2")
        self._adv_chevron.pack(side="right")
        self._adv_chevron.bind("<Button-1>", lambda _e: self._toggle_advanced())

        self._advanced_body = ctk.CTkFrame(adv_bar, fg_color="transparent")
        self._build_advanced_body(self._advanced_body)
        self._advanced_body.pack_forget()

        feat = ctk.CTkFrame(page, fg_color=th.bg_feature_bar, corner_radius=CARD_RADIUS)
        feat.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        feat.grid_columnconfigure((0, 1, 2, 3), weight=1)
        specs = [
            ("🛡", "feat_security", "feat_security_1", "feat_security_2"),
            ("🔒", "feat_easy", "feat_easy_1", "feat_easy_2"),
            ("⚡", "feat_fast", "feat_fast_1", "feat_fast_2"),
            ("</>", "feat_dev", "feat_dev_1", "feat_dev_2"),
        ]
        for col, (icon, tk_, l1, l2) in enumerate(specs):
            fc = FeatureCard(feat, th, icon, t(tk_, self.lang), t(l1, self.lang), t(l2, self.lang))
            fc.grid(row=0, column=col, sticky="nw", padx=24, pady=22)

    def _build_advanced_body(self, parent: ctk.CTkFrame) -> None:
        th = self.theme
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(fill="x", padx=24, pady=(0, 20))

        SectionHeader(wrap, th, t("adv_section_mcp", self.lang)).pack(anchor="w", pady=(0, 12))
        ctk.CTkLabel(wrap, text=t("mcp_mode", self.lang), font=font(TYPO.label, "bold"), text_color=th.text_title, anchor="w").pack(anchor="w", pady=(0, 8))
        self._mcp_mode = ctk.CTkComboBox(wrap, values=list(MCP_MODES), height=INPUT_HEIGHT, font=font(TYPO.body))
        self._mcp_mode.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(wrap, text=t("git_executable", self.lang), font=font(TYPO.label, "bold"), text_color=th.text_title, anchor="w").pack(anchor="w", pady=(0, 8))
        self._git_exe = ctk.CTkComboBox(wrap, values=["git", "git.exe"], height=INPUT_HEIGHT, font=font(TYPO.body))
        self._git_exe.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(wrap, text=t("git_hint", self.lang), font=font(TYPO.hint), text_color=th.text_hint, anchor="w").pack(anchor="w", pady=(0, 16))

        SectionHeader(wrap, th, t("adv_section_limits", self.lang)).pack(anchor="w", pady=(0, 12))
        self._max_file_mb = FormField(wrap, th, t("max_file_mb", self.lang))
        self._max_file_mb.pack(fill="x", pady=6)
        self._max_patch_kb = FormField(wrap, th, t("max_patch_kb", self.lang))
        self._max_patch_kb.pack(fill="x", pady=6)
        sw_row = ctk.CTkFrame(wrap, fg_color="transparent")
        sw_row.pack(fill="x", pady=8)
        ctk.CTkLabel(sw_row, text=t("allow_dirty", self.lang), font=font(TYPO.body), text_color=th.text).pack(side="left")
        self._dirty_switch = ctk.CTkSwitch(sw_row, text="")
        self._dirty_switch.pack(side="right")

        SectionHeader(wrap, th, t("adv_section_logging", self.lang)).pack(anchor="w", pady=(16, 12))
        ctk.CTkLabel(wrap, text=t("log_level", self.lang), font=font(TYPO.label, "bold"), text_color=th.text_title, anchor="w").pack(anchor="w", pady=(0, 8))
        self._log_level = ctk.CTkComboBox(wrap, values=["DEBUG", "INFO", "WARNING", "ERROR"], height=INPUT_HEIGHT, font=font(TYPO.body))
        self._log_level.pack(fill="x", pady=(0, 12))
        self._adv_cmd_to = FormField(wrap, th, t("cmd_timeout", self.lang))
        self._adv_cmd_to.pack(fill="x", pady=6)
        self._adv_txt_to = FormField(wrap, th, t("text_timeout", self.lang))
        self._adv_txt_to.pack(fill="x", pady=6)
        self._adv_max_out = FormField(wrap, th, t("max_output", self.lang))
        self._adv_max_out.pack(fill="x", pady=6)
        self._adv_max_search = FormField(wrap, th, t("max_search", self.lang))
        self._adv_max_search.pack(fill="x", pady=6)
        self._adv_audit = FormField(wrap, th, t("audit_path", self.lang))
        self._adv_audit.pack(fill="x", pady=6)

        lr = ctk.CTkFrame(wrap, fg_color="transparent")
        lr.pack(fill="x", pady=8)
        ctk.CTkLabel(lr, text=t("secret_level", self.lang), font=font(TYPO.body), text_color=th.text).pack(side="left")
        self._secret_level = ctk.CTkComboBox(lr, values=["low", "medium", "high"], width=140, height=INPUT_HEIGHT, font=font(TYPO.body))
        self._secret_level.pack(side="right")
        self._secret_level.set("medium")

        SectionHeader(wrap, th, t("tunnel_section", self.lang)).pack(anchor="w", pady=(16, 8))
        self._t_path = FormField(wrap, th, t("tunnel_path", self.lang))
        self._t_path.pack(fill="x", pady=4)
        self._t_id = FormField(wrap, th, t("tunnel_id", self.lang))
        self._t_id.pack(fill="x", pady=4)
        self._t_profile = FormField(wrap, th, t("tunnel_profile", self.lang))
        self._t_profile.pack(fill="x", pady=4)
        self._t_key = FormField(wrap, th, t("tunnel_key", self.lang))
        self._t_key.pack(fill="x", pady=4)
        self._t_key.configure_entry(show="*")
        sw = ctk.CTkFrame(wrap, fg_color="transparent")
        sw.pack(fill="x", pady=8)
        self._tunnel_sw = ctk.CTkSwitch(sw, text=t("enable_tunnel", self.lang))
        self._tunnel_sw.pack(side="left")

        SectionHeader(wrap, th, t("adv_section_other", self.lang)).pack(anchor="w", pady=(16, 12))
        self._auto_sw = ctk.CTkSwitch(wrap, text=t("auto_start", self.lang))
        self._auto_sw.pack(anchor="w", pady=(0, 12))
        ctk.CTkLabel(wrap, text=t("start_command", self.lang), font=font(TYPO.label, "bold"), text_color=th.text_title, anchor="w").pack(anchor="w", pady=(0, 8))
        cmd_row = ctk.CTkFrame(wrap, fg_color="transparent")
        cmd_row.pack(fill="x")
        cmd_row.grid_columnconfigure(0, weight=1)
        self._cmd_box = ctk.CTkEntry(cmd_row, height=36, font=font(TYPO.hint), fg_color=th.bg_input, border_color=th.border)
        self._cmd_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._cmd_box.configure(state="readonly")
        ctk.CTkButton(cmd_row, text=t("copy", self.lang), width=64, height=36, command=self._copy_cmd).grid(row=0, column=1)
        ctk.CTkButton(
            wrap, text=t("reset_default", self.lang), fg_color="transparent",
            text_color=th.accent, command=self._reset_defaults,
        ).pack(anchor="w", pady=(16, 0))

    def _toggle_advanced(self) -> None:
        self._advanced_open = not self._advanced_open
        if self._advanced_open:
            self._advanced_body.pack(fill="x", after=self._adv_head)
            self._adv_chevron.configure(text="▲")
            self._adv_hint.pack_forget()
        else:
            self._advanced_body.pack_forget()
            self._adv_chevron.configure(text="▼")
            self._adv_hint.pack(side="left")

    def _save_and_apply(self) -> None:
        if self._save() is not None:
            self._restart_mcp()

    def _go_test(self) -> None:
        self._show("test")
        self._run_test()

    # ── 2 MCP ──────────────────────────────────────────────

    def _page_mcp(self) -> None:
        page = self._pages["mcp"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)
        card = self._card(page)
        card.grid(row=0, column=0, sticky="nsew")
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="both", expand=True)
        self._page_header(wrap, "mcp_title", "mcp_sub")

        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.pack(fill="x", padx=24, pady=8)
        th = self.theme
        ctk.CTkButton(btns, text=t("start", self.lang), fg_color=th.accent, command=self._start_mcp).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text=t("stop", self.lang), command=lambda: self.process_manager.stop(self.process_manager.mcp)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text=t("restart", self.lang), command=self._restart_mcp).pack(side="left")

        st = ctk.CTkFrame(wrap, fg_color=th.bg_app, corner_radius=12)
        st.pack(fill="x", padx=24, pady=16)
        self._mcp_uptime = InfoRow(st, th, t("uptime", self.lang))
        self._mcp_uptime.pack(fill="x", padx=16, pady=8)
        self._mcp_pid = InfoRow(st, th, t("pid", self.lang))
        self._mcp_pid.pack(fill="x", padx=16, pady=8)
        self._mcp_transport = InfoRow(st, th, t("transport", self.lang))
        self._mcp_transport.pack(fill="x", padx=16, pady=8)
        self._mcp_version = InfoRow(st, th, t("version", self.lang))
        self._mcp_version.pack(fill="x", padx=16, pady=8)

        qa = ctk.CTkFrame(wrap, fg_color="transparent")
        qa.pack(fill="x", padx=24, pady=8)
        ctk.CTkButton(qa, text=t("open_logs", self.lang), command=lambda: self._show("logs")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(qa, text=t("test_connection", self.lang), command=lambda: self._show("test")).pack(side="left")

    # ── 3 Test ─────────────────────────────────────────────

    def _page_test(self) -> None:
        page = self._pages["test"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)
        card = self._card(page)
        card.grid(row=0, column=0, sticky="nsew")
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="both", expand=True)
        self._page_header(wrap, "test_title", "test_sub")

        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(row, text=t("client_sim", self.lang), font=font(14), text_color=self.theme.text).pack(side="left", padx=(0, 8))
        self._client_sim = ctk.CTkComboBox(row, values=["ChatGPT", "Cursor", "Claude Desktop", "Generic MCP"], width=200)
        self._client_sim.pack(side="left", padx=(0, 16))
        ctk.CTkButton(row, text=t("start_test", self.lang), fg_color=self.theme.accent, command=self._run_test).pack(side="left")

        cl = ctk.CTkFrame(wrap, fg_color=self.theme.bg_app, corner_radius=12)
        cl.pack(fill="x", padx=24, pady=16)
        self._checks: dict[str, ChecklistRow] = {}
        for key, lk in [
            ("connection", "chk_connection"),
            ("handshake", "chk_handshake"),
            ("tools", "chk_tools"),
            ("read", "chk_read"),
            ("search", "chk_search"),
            ("git", "chk_git"),
        ]:
            r = ChecklistRow(cl, self.theme, t(lk, self.lang))
            r.pack(fill="x", padx=16, pady=6)
            self._checks[key] = r

    # ── 4 Repo ─────────────────────────────────────────────

    def _page_repo(self) -> None:
        page = self._pages["repo"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)
        card = self._card(page)
        card.grid(row=0, column=0, sticky="nsew")
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="both", expand=True)
        self._page_header(wrap, "repo_title", "repo_sub")

        th = self.theme
        cur = ctk.CTkFrame(wrap, fg_color=th.bg_app, corner_radius=12)
        cur.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(cur, text=t("current_repo", self.lang), font=font(14, "bold"), text_color=th.text, anchor="w").pack(anchor="w", padx=16, pady=(12, 4))
        self._current_repo_lbl = ctk.CTkLabel(cur, text="-", font=font(13), text_color=th.text_muted, anchor="w")
        self._current_repo_lbl.pack(anchor="w", padx=16, pady=(0, 12))

        ctk.CTkLabel(wrap, text=t("trusted_repos", self.lang), font=font(14, "bold"), text_color=th.text, anchor="w").pack(anchor="w", padx=24, pady=(12, 6))
        self._trusted_list = ctk.CTkFrame(wrap, fg_color=th.bg_app, corner_radius=12)
        self._trusted_list.pack(fill="x", padx=24, pady=(0, 8))

        ctk.CTkButton(wrap, text=f"+ {t('add_repo', self.lang)}", fg_color="transparent", border_width=1, border_color=th.border, command=self._browse_repo).pack(anchor="w", padx=24, pady=8)

        self._repo_status = ctk.CTkTextbox(wrap, height=160, font=font(13))
        self._repo_status.pack(fill="x", padx=24, pady=8)

        act = ctk.CTkFrame(wrap, fg_color="transparent")
        act.pack(fill="x", padx=24, pady=8)
        ctk.CTkButton(act, text=t("open_finder", self.lang), command=self._open_repo).pack(side="left", padx=(0, 8))
        ctk.CTkButton(act, text=t("check_status", self.lang), command=self._refresh_git_status).pack(side="left")

    # ── 5 Security ───────────────────────────────────────

    def _page_security(self) -> None:
        page = self._pages["security"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)
        card = self._card(page)
        card.grid(row=0, column=0, sticky="nsew")
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="both", expand=True)
        self._page_header(wrap, "security_title", "security_sub")
        th = self.theme

        ctk.CTkLabel(wrap, text=t("sensitive_filter", self.lang), font=font(14, "bold"), text_color=th.text, anchor="w").pack(anchor="w", padx=24, pady=(0, 6))
        self._deny_box = ctk.CTkTextbox(wrap, height=120, font=font(12))
        self._deny_box.pack(fill="x", padx=24, pady=(0, 12))
        self._deny_box.insert("1.0", "\n".join(DEFAULT_READ_DENY_PATTERNS[:12]))
        self._deny_box.configure(state="disabled")

        sr = ctk.CTkFrame(wrap, fg_color="transparent")
        sr.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(sr, text=t("secret_detection", self.lang), font=font(14), text_color=th.text).pack(side="left")
        self._secret_sw = ctk.CTkSwitch(sr, text="")
        self._secret_sw.pack(side="right")
        self._secret_sw.select()
        self._secret_sw.configure(state="disabled")

        self._secret_level_info = InfoRow(wrap, th, t("secret_level", self.lang))
        self._secret_level_info.pack(fill="x", padx=24, pady=4)
        self._secret_level_info.set("medium")

        for lk, sw_attr in [("block_symlink", "_sw_symlink"), ("restrict_repo", "_sw_restrict")]:
            row = ctk.CTkFrame(wrap, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=6)
            ctk.CTkLabel(row, text=t(lk, self.lang), font=font(14), text_color=th.text).pack(side="left")
            sw = ctk.CTkSwitch(row, text="")
            sw.pack(side="right")
            sw.select()
            sw.configure(state="disabled")
            setattr(self, sw_attr, sw)

        rep = ctk.CTkFrame(wrap, fg_color=th.bg_app, corner_radius=12)
        rep.pack(fill="x", padx=24, pady=16)
        ctk.CTkLabel(rep, text=t("security_report", self.lang), font=font(14, "bold"), text_color=th.text).pack(anchor="w", padx=16, pady=(12, 8))
        self._scan_time = InfoRow(rep, th, t("last_scan", self.lang))
        self._scan_time.pack(fill="x", padx=16, pady=4)
        self._scan_issues = InfoRow(rep, th, t("issues_found", self.lang))
        self._scan_issues.pack(fill="x", padx=16, pady=(4, 12))

    # ── Logs ───────────────────────────────────────────

    def _page_logs(self) -> None:
        page = self._pages["logs"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)
        card = self._card(page)
        card.grid(row=0, column=0, sticky="nsew")
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="both", expand=True)
        self._page_header(wrap, "logs_title", "logs_sub")

        tabs = ctk.CTkTabview(wrap, height=36)
        tabs.pack(fill="x", padx=24, pady=(0, 8))
        tabs.add(t("log_mcp", self.lang))
        tabs.add(t("log_operation", self.lang))
        tabs.add(t("log_error", self.lang))
        self._log_tabs = tabs

        toolbar = ctk.CTkFrame(wrap, fg_color="transparent")
        toolbar.pack(fill="x", padx=24, pady=4)
        ctk.CTkLabel(toolbar, text=t("log_filter", self.lang), font=font(13)).pack(side="left", padx=(0, 6))
        self._log_filter = ctk.CTkComboBox(toolbar, values=["ALL", "INFO", "WARNING", "ERROR"], width=100)
        self._log_filter.pack(side="left", padx=(0, 12))
        self._log_search = ctk.CTkEntry(toolbar, placeholder_text=t("log_search", self.lang), width=160, height=32)
        self._log_search.pack(side="left", padx=(0, 8))
        ctk.CTkButton(toolbar, text=t("log_refresh", self.lang), width=72, height=32, command=self._refresh_logs).pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text=t("log_clear", self.lang), width=72, height=32, command=self._clear_logs).pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text=t("log_export", self.lang), width=88, height=32, command=self._export_logs).pack(side="right")

        self._log_view = ctk.CTkTextbox(wrap, font=font(13))
        self._log_view.pack(fill="both", expand=True, padx=24, pady=(8, 20))

    # ── 8 About ──────────────────────────────────────────

    def _page_about(self) -> None:
        page = self._pages["about"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)
        card = self._card(page)
        card.grid(row=0, column=0, sticky="nsew")
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="both", expand=True)
        ctk.CTkLabel(wrap, text="📦", font=font(64)).pack(pady=(40, 12))
        ctk.CTkLabel(wrap, text="Local Repo MCP", font=font(26, "bold"), text_color=self.theme.text).pack()
        ctk.CTkLabel(wrap, text=f"v{VERSION}", font=font(14), text_color=self.theme.text_muted).pack(pady=(4, 16))
        ctk.CTkLabel(wrap, text=t("about_desc", self.lang), font=font(14), text_color=self.theme.text_muted).pack(pady=(0, 24))

        links = ctk.CTkFrame(wrap, fg_color="transparent")
        links.pack()
        ctk.CTkButton(links, text=t("github", self.lang), fg_color="transparent", border_width=1, border_color=self.theme.border, command=lambda: webbrowser.open("https://github.com/cloud-Xolt/local-repo-mcp")).pack(pady=6, ipadx=20)
        ctk.CTkButton(links, text=t("documentation", self.lang), fg_color="transparent", border_width=1, border_color=self.theme.border, command=lambda: webbrowser.open(f"file://{(PROJECT_ROOT / 'README.zh-CN.md').resolve()}")).pack(pady=6, ipadx=20)
        ctk.CTkButton(links, text=t("report_issue", self.lang), fg_color="transparent", border_width=1, border_color=self.theme.border, command=lambda: webbrowser.open("https://github.com/cloud-Xolt/local-repo-mcp/issues")).pack(pady=6, ipadx=20)
        ctk.CTkLabel(wrap, text=t("copyright", self.lang), font=font(12), text_color=self.theme.text_muted).pack(pady=(32, 20))

    # ── logic ──────────────────────────────────────────────

    def _show(self, key: str) -> None:
        self._page = key
        for k, p in self._pages.items():
            p.grid() if k == key else p.grid_remove()
        th = self.theme
        for k, btn in self._nav_btns.items():
            if k == key:
                btn.configure(fg_color=th.bg_nav_active, text_color=th.nav_active_text)
            else:
                btn.configure(fg_color="transparent", text_color=th.text)
        if key == "repo":
            self._refresh_trusted()
            self._refresh_git_status()
        if key == "logs":
            self._refresh_logs()

    def _load(self) -> None:
        c = self.config_data
        self._repo_path.delete(0, "end")
        self._repo_path.insert(0, c.repo_root)
        self._branch_field.set(git_branch(c.repo_root, c.git_executable))
        self._service_port.set(str(c.service_port))
        self._service_mode.set(t("service_mode_stdio", self.lang))
        self._mcp_mode.set(c.mcp_mode)
        self._selected_mode = c.mcp_mode
        self._git_exe.set(c.git_executable)
        self._max_file_mb.set(str(max(1, c.max_file_bytes // 1024 // 1024)))
        self._max_patch_kb.set(str(max(1, c.max_patch_bytes // 1024)))
        if c.allow_dirty_worktree:
            self._dirty_switch.select()
        self._log_level.set(c.log_level)
        self._secret_level.set(c.secret_detection_level)
        self._adv_cmd_to.set(str(c.command_timeout))
        self._adv_txt_to.set(str(c.text_timeout))
        self._adv_max_out.set(str(c.max_output_bytes))
        self._adv_max_search.set(str(c.max_search_results))
        self._adv_audit.set(c.audit_log)
        self._t_path.set(c.tunnel_client_path)
        self._t_id.set(c.tunnel_id)
        self._t_profile.set(c.tunnel_profile)
        if c.use_tunnel:
            self._tunnel_sw.select()
        if c.auto_start_mcp:
            self._auto_sw.select()
        cmd = start_command_text()
        self._cmd_box.configure(state="normal")
        self._cmd_box.delete(0, "end")
        self._cmd_box.insert(0, cmd)
        self._cmd_box.configure(state="readonly")
        self._refresh_panel()

    def _collect(self) -> AppConfig:
        mb = int(self._max_file_mb.get().strip() or "1")
        kb = int(self._max_patch_kb.get().strip() or "1")
        mode = self._mcp_mode.get().strip()
        return AppConfig(
            repo_root=self._repo_path.get().strip(),
            mcp_mode=mode,
            max_file_bytes=mb * 1024 * 1024,
            max_patch_bytes=kb * 1024,
            max_search_results=int(self._adv_max_search.get().strip()),
            max_output_bytes=int(self._adv_max_out.get().strip()),
            allow_dirty_worktree=bool(self._dirty_switch.get()),
            audit_log=self._adv_audit.get().strip(),
            tunnel_client_path=self._t_path.get().strip(),
            tunnel_id=self._t_id.get().strip(),
            tunnel_profile=self._t_profile.get().strip() or "local-repo",
            control_plane_api_key=self._t_key.get().strip(),
            auto_start_mcp=bool(self._auto_sw.get()),
            use_tunnel=bool(self._tunnel_sw.get()),
            service_port=int(self._service_port.get().strip()),
            service_mode="stdio",
            git_executable=self._git_exe.get().strip(),
            log_level=self._log_level.get().strip(),
            command_timeout=int(self._adv_cmd_to.get().strip()),
            text_timeout=int(self._adv_txt_to.get().strip()),
            secret_detection_level=self._secret_level.get().strip(),
        )

    def _refresh_panel(self) -> None:
        c = self.config_data
        pm = self.process_manager
        running = pm.mcp.running
        th = self.theme
        branch = git_branch(c.repo_root, c.git_executable)
        repo_name = Path(c.repo_root).name if c.repo_root else "-"
        port = self._service_port.get().strip() or str(c.service_port)
        branch_display = self._branch_field.get().strip() or branch
        self._pi_mcp.set(f"stdio://localhost:{port}  ›", link=True, theme=th)
        self._pi_port.set(port)
        self._pi_repo.set(repo_name)
        self._pi_branch.set(branch_display)
        self._mcp_uptime.set(pm.mcp.uptime)
        self._mcp_pid.set(pm.mcp.pid)
        self._mcp_transport.set("stdio")
        self._mcp_version.set(VERSION)
        self._current_repo_lbl.configure(text=c.repo_root)
        self._scan_time.set(self._last_scan)
        self._scan_issues.set(str(self._issues))
        if running:
            self._run_badge.configure(text=t("running", self.lang), text_color=th.success, fg_color=th.success_bg)
            self._sb_dot.configure(text_color=th.success)
            self._sb_status.configure(text=f"{t('service_status', self.lang)}: {t('running', self.lang)}")
        else:
            self._run_badge.configure(text=t("stopped", self.lang), text_color=th.text_muted, fg_color=th.border)
            self._sb_dot.configure(text_color=th.text_muted)
            self._sb_status.configure(text=f"{t('service_status', self.lang)}: {t('stopped', self.lang)}")

    def _refresh_trusted(self) -> None:
        for w in self._trusted_list.winfo_children():
            w.destroy()
        path = self._repo_path.get().strip()
        if not path:
            return
        th = self.theme
        row = ctk.CTkFrame(self._trusted_list, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=10)
        row.grid_columnconfigure(0, weight=1)
        name = Path(path).name
        branch = git_branch(path, self._git_exe.get().strip())
        ctk.CTkLabel(row, text=f"{name}  ·  {path}", font=font(13), text_color=th.text, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(row, text=f"{t('branch', self.lang)}: {branch}", font=font(12), text_color=th.text_muted, anchor="w").grid(row=1, column=0, sticky="w")
        ctk.CTkButton(row, text=t("switch_repo", self.lang), width=72, height=30, fg_color=th.accent, command=lambda: None).grid(row=0, column=1, rowspan=2, padx=8)

    def _save(self, silent: bool = False) -> AppConfig | None:
        try:
            cfg = self._collect()
        except ValueError:
            if not silent:
                messagebox.showerror("Error", "Invalid number")
            return None
        errs = cfg.validate()
        if errs and not silent:
            messagebox.showerror("Error", "\n".join(errs))
            return None
        save_all(cfg)
        self.config_data = cfg
        self._refresh_panel()
        if not silent:
            messagebox.showinfo("OK", t("saved", self.lang))
        return cfg

    def _copy_cmd(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(start_command_text())
        messagebox.showinfo("OK", t("copied", self.lang))

    def _browse_repo(self) -> None:
        p = filedialog.askdirectory()
        if p:
            self._repo_path.delete(0, "end")
            self._repo_path.insert(0, p)
            self._branch_field.set(git_branch(p, self._git_exe.get().strip()))

    def _open_repo(self) -> None:
        p = self._repo_path.get().strip()
        if p and Path(p).exists():
            os.startfile(p)  # noqa: S606

    def _refresh_git_status(self) -> None:
        repo = self._repo_path.get().strip()
        git = self._git_exe.get().strip() or "git"
        try:
            r = subprocess.run([git, "-C", repo, "status", "--short"], capture_output=True, text=True, timeout=15, check=False)
            text = r.stdout.strip() or "(clean)"
        except Exception as exc:
            text = str(exc)
        self._repo_status.delete("1.0", "end")
        self._repo_status.insert("1.0", text)

    def _run_test(self) -> None:
        for c in self._checks.values():
            c.set_pending()
        cfg = self._save(silent=True)
        if cfg is None:
            for c in self._checks.values():
                c.set_fail()
            return

        def step(key: str, ok: bool) -> None:
            self.after(0, lambda: self._checks[key].set_ok(t("ok", self.lang)) if ok else self._checks[key].set_fail())

        def worker() -> None:
            step("connection", Path(cfg.repo_root).exists())
            time.sleep(0.2)
            step("handshake", cfg.mcp_mode in MCP_MODES)
            time.sleep(0.2)
            step("tools", True)
            time.sleep(0.2)
            step("read", (Path(cfg.repo_root) / "README.md").exists() or (Path(cfg.repo_root)).exists())
            time.sleep(0.2)
            step("search", shutil.which("rg") is not None)
            time.sleep(0.2)
            step("git", shutil.which(cfg.git_executable) is not None)
            self._last_scan = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._issues = 0
            self.after(0, self._refresh_panel)

        threading.Thread(target=worker, daemon=True).start()

    def _worker(self, fn) -> None:
        if self._busy:
            return
        self._busy = True

        def run() -> None:
            try:
                fn()
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Error", str(exc)))
            finally:
                self.after(0, lambda: setattr(self, "_busy", False))

        threading.Thread(target=run, daemon=True).start()

    def _start_mcp(self) -> None:
        cfg = self._save(silent=True)
        if cfg is None:
            return
        self._worker(lambda: (self.process_manager.start_mcp(cfg), self.after(0, self._refresh_panel)))

    def _restart_mcp(self) -> None:
        cfg = self._save(silent=True)
        if cfg is None:
            return
        self._worker(lambda: (self.process_manager.restart_mcp(cfg), self.after(0, self._refresh_panel)))

    def _reset_defaults(self) -> None:
        self.config_data = reset_defaults()
        self._load()

    def _refresh_logs(self) -> None:
        tab = self._log_tabs.get()
        flt = self._log_filter.get()
        q = self._log_search.get().strip().lower()
        if t("log_operation", self.lang) in tab or "Operation" in tab:
            lines, self._audit_offset = self.process_manager.tail_audit_log(self.config_data.audit_log, 0)
            raw = lines
        elif t("log_error", self.lang) in tab or "Error" in tab:
            raw = [l for l in self.process_manager.get_recent_logs(self.process_manager.mcp) if "error" in l.lower() or "fail" in l.lower()]
        else:
            raw = self.process_manager.get_recent_logs(self.process_manager.mcp)
        if flt != "ALL":
            raw = [l for l in raw if flt.lower() in l.lower()]
        if q:
            raw = [l for l in raw if q in l.lower()]
        self._log_view.delete("1.0", "end")
        self._log_view.insert("1.0", "\n".join(raw) if raw else "(empty)")

    def _clear_logs(self) -> None:
        self._log_view.delete("1.0", "end")

    def _export_logs(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".log", filetypes=[("Log", "*.log"), ("Text", "*.txt")])
        if path:
            Path(path).write_text(self._log_view.get("1.0", "end"), encoding="utf-8")

    def _on_log(self, _src: str, _line: str) -> None:
        if self._page == "logs":
            self.after(0, self._refresh_logs)

    def _snapshot_form(self) -> dict:
        snap: dict = {"advanced_open": self._advanced_open, "page": self._page}
        if hasattr(self, "_repo_path"):
            snap["repo_root"] = self._repo_path.get()
        if hasattr(self, "_branch_field"):
            snap["branch"] = self._branch_field.get()
        if hasattr(self, "_service_port"):
            snap["service_port"] = self._service_port.get()
        for attr in ("_mcp_mode", "_git_exe", "_log_level", "_secret_level"):
            w = getattr(self, attr, None)
            if w is not None:
                snap[attr] = w.get()
        for attr in ("_max_file_mb", "_max_patch_kb", "_adv_cmd_to", "_adv_txt_to", "_adv_max_out", "_adv_max_search", "_adv_audit"):
            w = getattr(self, attr, None)
            if w is not None:
                snap[attr] = w.get()
        for attr in ("_t_path", "_t_id", "_t_profile", "_t_key"):
            w = getattr(self, attr, None)
            if w is not None:
                snap[attr] = w.get()
        for attr, key in (("_dirty_switch", "dirty"), ("_tunnel_sw", "tunnel"), ("_auto_sw", "auto_start")):
            w = getattr(self, attr, None)
            if w is not None:
                snap[key] = bool(w.get())
        if hasattr(self, "_log_tabs"):
            cur = self._log_tabs.get()
            for i, k in enumerate(["log_mcp", "log_operation", "log_error"]):
                if cur == t(k, self.lang):
                    snap["log_tab_idx"] = i
                    break
        return snap

    def _restore_form(self, snap: dict) -> None:
        if "repo_root" in snap:
            self._repo_path.delete(0, "end")
            self._repo_path.insert(0, snap["repo_root"])
        if "branch" in snap:
            self._branch_field.set(snap["branch"])
        if "service_port" in snap:
            self._service_port.set(snap["service_port"])
        mapping = {
            "_mcp_mode": "_mcp_mode",
            "_git_exe": "_git_exe",
            "_log_level": "_log_level",
            "_secret_level": "_secret_level",
            "_max_file_mb": "_max_file_mb",
            "_max_patch_kb": "_max_patch_kb",
            "_adv_cmd_to": "_adv_cmd_to",
            "_adv_txt_to": "_adv_txt_to",
            "_adv_max_out": "_adv_max_out",
            "_adv_max_search": "_adv_max_search",
            "_adv_audit": "_adv_audit",
            "_t_path": "_t_path",
            "_t_id": "_t_id",
            "_t_profile": "_t_profile",
            "_t_key": "_t_key",
        }
        for snap_key, attr in mapping.items():
            if snap_key in snap:
                getattr(self, attr).set(snap[snap_key])
        if snap.get("dirty"):
            self._dirty_switch.select()
        if snap.get("tunnel"):
            self._tunnel_sw.select()
        if snap.get("auto_start"):
            self._auto_sw.select()
        self._service_mode.set(t("service_mode_stdio", self.lang))
        cmd = start_command_text()
        self._cmd_box.configure(state="normal")
        self._cmd_box.delete(0, "end")
        self._cmd_box.insert(0, cmd)
        self._cmd_box.configure(state="readonly")
        want_open = snap.get("advanced_open", False)
        if want_open and not self._advanced_open:
            self._toggle_advanced()
        elif not want_open and self._advanced_open:
            self._toggle_advanced()
        if "log_tab_idx" in snap and hasattr(self, "_log_tabs"):
            names = [t("log_mcp", self.lang), t("log_operation", self.lang), t("log_error", self.lang)]
            idx = snap["log_tab_idx"]
            if 0 <= idx < len(names):
                self._log_tabs.set(names[idx])

    def _rebuild_pages(self) -> None:
        self._advanced_open = False
        for page in self._pages.values():
            for child in page.winfo_children():
                child.destroy()
        self._page_general()
        self._page_repo()
        self._page_security()
        self._page_mcp()
        self._page_test()
        self._page_logs()
        self._page_about()

    def _lang(self, lang: Lang) -> None:
        if lang == self.lang:
            return
        snap = self._snapshot_form()
        page = snap.get("page", self._page)
        self.lang = lang
        self._ = bind(lang)
        th = self.theme
        self._lang_zh.configure(text_color=th.header_btn_active if lang == "zh" else th.header_btn)
        self._lang_en.configure(text_color=th.header_btn_active if lang == "en" else th.header_btn)
        for key, lk in NAV:
            self._nav_btns[key].configure(text=f"  {t(lk, self.lang)}")
        self._rebuild_pages()
        self._restore_form(snap)
        self._show(page)
        self._refresh_panel()

    def _toggle_theme(self) -> None:
        if self.theme is LIGHT:
            ctk.set_appearance_mode("dark")
            self.theme = DARK
            self._theme_btn.configure(text="🌙")
        else:
            ctk.set_appearance_mode("light")
            self.theme = LIGHT
            self._theme_btn.configure(text="☀")
        self.configure(fg_color=self.theme.bg_app)

    def _tick(self) -> None:
        self._refresh_panel()
        if self._page == "logs":
            self._refresh_logs()
        self.after(1000, self._tick)

    def on_closing(self) -> None:
        pm = self.process_manager
        if pm.mcp.running or pm.tunnel.running:
            if messagebox.askyesno("Exit", "Stop services and exit?"):
                pm.stop_all()
                self.destroy()
        else:
            self.destroy()


def main() -> None:
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    app = MCPControlApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
