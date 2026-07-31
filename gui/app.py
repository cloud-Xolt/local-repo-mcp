"""Local Repo MCP 控制面板 — 一键启动，全 GUI 操作。"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from gui.config import (
    MCP_MODES,
    AppConfig,
    lines_to_list,
    list_to_lines,
    load_config,
    save_all,
)
from gui import operations
from gui.components_panel import LocalComponentsPanel
from gui import local_registry
from gui.process_manager import ProcessManager

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

ACCENT = "#2563EB"
ACCENT_HOVER = "#1D4ED8"
SUCCESS = "#16A34A"
DANGER = "#DC2626"
MUTED = "#64748B"
TEXT = "#334155"
BG_APP = "#EEF2F7"
BG_CARD = "#FFFFFF"
BTN_SECONDARY = "#E2E8F0"
BTN_SECONDARY_HOVER = "#CBD5E1"
LOG_BG = "#F8FAFC"

SIZE_TITLE = 28
SIZE_SUBTITLE = 16
SIZE_SECTION = 16
SIZE_BODY = 15
SIZE_BTN_LG = 17
SIZE_FOOTER = 13
SIZE_LOG = 14
INPUT_HEIGHT = 38
BTN_HEIGHT = 40
BTN_HEIGHT_LG = 52


def _font(size: int, weight: str = "normal", family: str | None = None) -> ctk.CTkFont:
    kwargs: dict = {"size": size}
    if weight != "normal":
        kwargs["weight"] = weight
    if family:
        kwargs["family"] = family
    return ctk.CTkFont(**kwargs)


class StatusBadge(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, label: str) -> None:
        super().__init__(master, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BTN_SECONDARY)
        self.grid_columnconfigure(1, weight=1)
        self.dot = ctk.CTkLabel(self, text="●", font=ctk.CTkFont(size=22), text_color=MUTED)
        self.dot.grid(row=0, column=0, padx=(14, 6), pady=14)
        ctk.CTkLabel(self, text=label, font=_font(SIZE_SECTION, "bold"), text_color=TEXT).grid(
            row=0, column=1, sticky="w", pady=14
        )
        self.state = ctk.CTkLabel(self, text="已停止", font=_font(SIZE_BODY), text_color=MUTED)
        self.state.grid(row=0, column=2, padx=(0, 8), pady=14)
        self.uptime = ctk.CTkLabel(self, text="", font=_font(SIZE_BODY), text_color=MUTED)
        self.uptime.grid(row=0, column=3, padx=(0, 14), pady=14)

    def set_running(self, running: bool, uptime: str = "", state_text: str | None = None) -> None:
        if running:
            self.dot.configure(text_color=SUCCESS)
            self.state.configure(text=state_text or "运行中", text_color=SUCCESS)
            self.uptime.configure(text=uptime)
        else:
            self.dot.configure(text_color=MUTED if not state_text else DANGER)
            self.state.configure(text=state_text or "已停止", text_color=MUTED if not state_text else DANGER)
            self.uptime.configure(text=uptime if uptime else "")


class SectionTitle(ctk.CTkLabel):
    def __init__(self, master: ctk.CTkBaseClass, text: str) -> None:
        super().__init__(master, text=text, font=_font(SIZE_SECTION, "bold"), text_color=MUTED, anchor="w")


class MCPControlApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Local Repo MCP")
        self.geometry("1180x860")
        self.minsize(1000, 720)
        self.configure(fg_color=BG_APP)

        self.config_data = load_config()
        local_registry.ensure_local_layout(self.config_data)
        self.process_manager = ProcessManager(on_log=self._on_process_log)
        self._components_panel: LocalComponentsPanel | None = None
        self._audit_offset = 0
        self._busy = False

        self._build_layout()
        self._load_form()
        self._refresh_env_check()
        self._tick()

        if self.config_data.auto_start_mcp:
            self.after(800, self._start_mcp)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        ctk.CTkLabel(header, text="Local Repo MCP", font=_font(SIZE_TITLE, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(
            header, text="本地组件统一纳管 · 进程 / 配置 / 数据 全在 GUI", font=_font(SIZE_SUBTITLE), text_color=MUTED
        ).pack(anchor="w", pady=(4, 0))

        status_bar = ctk.CTkFrame(self, fg_color="transparent")
        status_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        status_bar.grid_columnconfigure((0, 1, 2), weight=1)
        self.mcp_status = StatusBadge(status_bar, "MCP Server")
        self.mcp_status.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.tunnel_status = StatusBadge(status_bar, "Tunnel Client")
        self.tunnel_status.grid(row=0, column=1, sticky="ew", padx=4)
        self.config_status = StatusBadge(status_bar, "本地配置")
        self.config_status.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        self.tabview = ctk.CTkTabview(self, fg_color=BG_CARD, segmented_button_fg_color=BTN_SECONDARY)
        self.tabview.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 12))
        self.tabview.add("概览")
        self.tabview.add("本地组件")
        self.tabview.add("Tunnel")
        self.tabview.add("配置")
        self.tabview.add("运维")
        self.tabview.add("日志")

        self._build_overview_tab(self.tabview.tab("概览"))
        self._build_local_components_tab(self.tabview.tab("本地组件"))
        self._build_tunnel_tab(self.tabview.tab("Tunnel"))
        self._build_settings_tab(self.tabview.tab("配置"))
        self._build_ops_tab(self.tabview.tab("运维"))
        self._build_logs_tab(self.tabview.tab("日志"))

        ctk.CTkLabel(
            self,
            text="本地侧组件/配置均在 GUI 纳管 · Cloud 侧仅需 OpenAI 控制台创建 Tunnel 与 ChatGPT App",
            font=_font(SIZE_FOOTER),
            text_color=MUTED,
        ).grid(row=3, column=0, sticky="w", padx=22, pady=(0, 12))

    def _build_overview_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.grid(row=0, column=0, sticky="ew", padx=16, pady=16)
        actions.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(
            actions,
            text="▶  一键启动 MCP\n（本地调试）",
            height=BTN_HEIGHT_LG,
            font=_font(SIZE_BTN_LG, "bold"),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._start_mcp,
        ).grid(row=0, column=0, sticky="ew", padx=6, pady=6)

        ctk.CTkButton(
            actions,
            text="▶  一键启动 Tunnel + MCP\n（可选 · 接入 ChatGPT）",
            height=BTN_HEIGHT_LG,
            font=_font(SIZE_BTN_LG, "bold"),
            fg_color=SUCCESS,
            hover_color="#15803D",
            command=self._start_all,
        ).grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ctk.CTkButton(
            actions,
            text="■  全部停止",
            height=BTN_HEIGHT_LG,
            font=_font(SIZE_BTN_LG, "bold"),
            fg_color=DANGER,
            hover_color="#B91C1C",
            command=self._stop_all,
        ).grid(row=0, column=2, sticky="ew", padx=6, pady=6)

        opts = ctk.CTkFrame(parent, fg_color="transparent")
        opts.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        self.auto_start_mcp = ctk.CTkCheckBox(
            opts,
            text="下次打开 GUI 时自动启动 MCP",
            font=_font(SIZE_BODY),
            command=self._toggle_auto_start,
        )
        self.auto_start_mcp.pack(side="left", padx=4)
        if self.config_data.auto_start_mcp:
            self.auto_start_mcp.select()

        ctk.CTkButton(
            opts,
            text="保存配置",
            width=100,
            height=36,
            font=_font(SIZE_BODY),
            fg_color=BTN_SECONDARY,
            text_color=TEXT,
            hover_color=BTN_SECONDARY_HOVER,
            command=self._save_config,
        ).pack(side="right", padx=4)

        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        body.grid_columnconfigure((0, 1), weight=1)
        body.grid_rowconfigure(0, weight=1)

        env_card = ctk.CTkFrame(body, fg_color=LOG_BG, corner_radius=12, border_width=1, border_color=BTN_SECONDARY)
        env_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        env_card.grid_rowconfigure(1, weight=1)
        env_card.grid_columnconfigure(0, weight=1)
        hdr = ctk.CTkFrame(env_card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        hdr.grid_columnconfigure(0, weight=1)
        SectionTitle(hdr, "环境检查").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            hdr, text="刷新", width=72, height=32, font=_font(SIZE_BODY),
            fg_color=BTN_SECONDARY, text_color=TEXT, hover_color=BTN_SECONDARY_HOVER,
            command=self._refresh_env_check,
        ).grid(row=0, column=1)
        self.env_box = ctk.CTkTextbox(env_card, font=_font(SIZE_LOG, family="Consolas"), fg_color=LOG_BG)
        self.env_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        quick_card = ctk.CTkFrame(body, fg_color=LOG_BG, corner_radius=12, border_width=1, border_color=BTN_SECONDARY)
        quick_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        SectionTitle(quick_card, "快捷打开").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
        qf = ctk.CTkFrame(quick_card, fg_color="transparent")
        qf.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        for i, (label, cmd) in enumerate(
            [
                ("打开仓库目录", self._open_repo),
                ("打开项目目录", self._open_project),
                ("打开审计日志", self._open_audit),
                ("打开策略文件", self._open_policy),
            ]
        ):
            ctk.CTkButton(
                qf, text=label, height=BTN_HEIGHT, font=_font(SIZE_BODY),
                fg_color=BTN_SECONDARY, text_color=TEXT, hover_color=BTN_SECONDARY_HOVER,
                command=cmd,
            ).grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)
            qf.grid_columnconfigure(i % 2, weight=1)

    def _build_local_components_tab(self, parent: ctk.CTkFrame) -> None:
        self._components_panel = LocalComponentsPanel(
            parent,
            self,
            _font(SIZE_BODY),
            _font(SIZE_SECTION, "bold"),
            _font(SIZE_LOG, family="Consolas"),
        )

    def _build_tunnel_tab(self, parent: ctk.CTkFrame) -> None:
        """tunnel-client 本地纳管专页。"""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        for i, (text, cmd) in enumerate(
            [
                ("安装/更新到项目", self._install_tunnel),
                ("初始化 Profile", self._init_tunnel),
                ("Doctor 检查", self._run_doctor),
                ("启动 Tunnel", self._start_tunnel_only),
                ("停止 Tunnel", self._stop_tunnel),
                ("重启 Tunnel", self._restart_tunnel),
            ]
        ):
            ctk.CTkButton(
                toolbar, text=text, height=36, font=_font(SIZE_BODY),
                fg_color=BTN_SECONDARY, text_color=TEXT, hover_color=BTN_SECONDARY_HOVER,
                command=cmd,
            ).grid(row=0, column=i, padx=4, pady=4)

        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure((0, 1), weight=1)
        body.grid_rowconfigure(0, weight=1)

        status_card = ctk.CTkFrame(body, fg_color=LOG_BG, corner_radius=12, border_width=1, border_color=BTN_SECONDARY)
        status_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        status_card.grid_rowconfigure(1, weight=1)
        status_card.grid_columnconfigure(0, weight=1)
        hdr = ctk.CTkFrame(status_card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        hdr.grid_columnconfigure(0, weight=1)
        SectionTitle(hdr, "纳管状态").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            hdr, text="刷新", width=72, height=32, font=_font(SIZE_BODY),
            fg_color=BTN_SECONDARY, text_color=TEXT, hover_color=BTN_SECONDARY_HOVER,
            command=self._refresh_tunnel_status,
        ).grid(row=0, column=1)
        self.tunnel_info_box = ctk.CTkTextbox(status_card, font=_font(SIZE_LOG, family="Consolas"))
        self.tunnel_info_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        doc_card = ctk.CTkFrame(body, fg_color=LOG_BG, corner_radius=12, border_width=1, border_color=BTN_SECONDARY)
        doc_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        SectionTitle(doc_card, "说明").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
        ctk.CTkLabel(
            doc_card,
            text=(
                "tunnel-client 为可选项，仅 ChatGPT 接入需要。\n\n"
                "不启用时：仅运行 MCP Server 即可（Cursor/本地调试）。\n"
                "启用时：配置 Tunnel ID / API Key → 安装 → 初始化 → 启动。\n\n"
                "纳管内容：\n"
                "· 二进制 → bin/tunnel-client/\n"
                "· Profile → data/tunnel/profiles/\n"
                "· 状态 → data/tunnel/state.json\n\n"
                "ChatGPT 接入：配置 Tunnel ID / API Key →\n"
                "安装 → 初始化 Profile → Doctor → 启动 Tunnel"
            ),
            font=_font(SIZE_BODY),
            text_color=TEXT,
            justify="left",
            anchor="nw",
        ).grid(row=1, column=0, sticky="nw", padx=12, pady=(0, 12))

        quick = ctk.CTkFrame(body, fg_color="transparent")
        quick.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        for i, (label, cmd) in enumerate(
            [
                ("打开 bin 目录", self._open_tunnel_bin),
                ("打开 Profile 目录", self._open_tunnel_profiles),
                ("打开 data/tunnel", self._open_tunnel_data),
            ]
        ):
            ctk.CTkButton(
                quick, text=label, height=BTN_HEIGHT, font=_font(SIZE_BODY),
                fg_color=BTN_SECONDARY, text_color=TEXT, hover_color=BTN_SECONDARY_HOVER,
                command=cmd,
            ).grid(row=0, column=i, padx=4, pady=4)

        SectionTitle(body, "Doctor 输出").grid(row=2, column=0, columnspan=2, sticky="w", pady=(16, 4))
        self.tunnel_doctor_box = ctk.CTkTextbox(body, font=_font(SIZE_LOG, family="Consolas"), height=140)
        self.tunnel_doctor_box.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))

    def _build_settings_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        scroll.grid_columnconfigure(1, weight=1)
        font_body = _font(SIZE_BODY)
        font_label = _font(SIZE_BODY)
        row = 0

        SectionTitle(scroll, "仓库设置").grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 4))
        row += 1
        ctk.CTkLabel(scroll, text="仓库路径", font=font_label).grid(row=row, column=0, sticky="w", padx=8, pady=6)
        self.repo_root = ctk.CTkEntry(scroll, font=font_body, height=INPUT_HEIGHT)
        self.repo_root.grid(row=row, column=1, sticky="ew", padx=6, pady=6)
        ctk.CTkButton(scroll, text="浏览", width=72, command=self._browse_repo).grid(row=row, column=2, padx=8, pady=6)
        row += 1
        ctk.CTkLabel(scroll, text="运行模式", font=font_label).grid(row=row, column=0, sticky="w", padx=8, pady=6)
        self.mcp_mode = ctk.CTkComboBox(scroll, values=list(MCP_MODES), state="readonly", font=font_body, height=INPUT_HEIGHT)
        self.mcp_mode.grid(row=row, column=1, columnspan=2, sticky="ew", padx=6, pady=6)
        row += 1

        SectionTitle(scroll, "安全与审计").grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=(12, 4))
        row += 1
        for label, attr in [
            ("最大文件 (B)", "max_file_bytes"),
            ("最大 Patch (B)", "max_patch_bytes"),
            ("审计日志", "audit_log"),
            ("策略文件", "policy_rules"),
            ("Session 文件", "sessions_file"),
        ]:
            ctk.CTkLabel(scroll, text=label, font=font_label).grid(row=row, column=0, sticky="w", padx=8, pady=6)
            entry = ctk.CTkEntry(scroll, font=font_body, height=INPUT_HEIGHT)
            entry.grid(row=row, column=1, sticky="ew", padx=6, pady=6)
            setattr(self, attr, entry)
            if label == "策略文件":
                ctk.CTkButton(scroll, text="浏览", width=72, command=self._browse_policy_rules).grid(row=row, column=2, padx=8)
            elif label == "Session 文件":
                ctk.CTkButton(scroll, text="浏览", width=72, command=self._browse_sessions_file).grid(row=row, column=2, padx=8)
            row += 1

        self.allow_dirty = ctk.CTkCheckBox(scroll, text="允许 dirty worktree 时 apply patch", font=font_body)
        self.allow_dirty.grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=6)
        row += 1

        SectionTitle(scroll, "RBAC 用户角色").grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=(12, 4))
        row += 1
        ctk.CTkLabel(scroll, text="默认角色", font=font_label).grid(row=row, column=0, sticky="w", padx=8, pady=6)
        self.rbac_default_role = ctk.CTkEntry(scroll, font=font_body, height=INPUT_HEIGHT)
        self.rbac_default_role.grid(row=row, column=1, columnspan=2, sticky="ew", padx=6, pady=6)
        row += 1
        ctk.CTkLabel(scroll, text="用户:角色", font=font_label).grid(row=row, column=0, sticky="nw", padx=8, pady=6)
        self.rbac_users = ctk.CTkTextbox(scroll, font=font_body, height=80)
        self.rbac_users.grid(row=row, column=1, columnspan=2, sticky="ew", padx=6, pady=6)
        row += 1

        SectionTitle(scroll, "Git / 写入 / 测试").grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=(12, 4))
        row += 1
        ctk.CTkLabel(scroll, text="受保护分支").grid(row=row, column=0, sticky="nw", padx=8, pady=6)
        self.protected_branches = ctk.CTkTextbox(scroll, font=font_body, height=72)
        self.protected_branches.grid(row=row, column=1, columnspan=2, sticky="ew", padx=6, pady=6)
        row += 1
        ctk.CTkLabel(scroll, text="写入 deny").grid(row=row, column=0, sticky="nw", padx=8, pady=6)
        self.write_deny = ctk.CTkTextbox(scroll, font=font_body, height=80)
        self.write_deny.grid(row=row, column=1, columnspan=2, sticky="ew", padx=6, pady=6)
        row += 1
        ctk.CTkLabel(scroll, text="测试白名单").grid(row=row, column=0, sticky="nw", padx=8, pady=6)
        self.execute_allow = ctk.CTkTextbox(scroll, font=font_body, height=80)
        self.execute_allow.grid(row=row, column=1, columnspan=2, sticky="ew", padx=6, pady=6)
        row += 1

        SectionTitle(scroll, "Docker 沙箱").grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=(12, 4))
        row += 1
        for label, attr in [
            ("内存", "sandbox_memory"),
            ("CPU", "sandbox_cpus"),
            ("tmpfs (MB)", "sandbox_tmpfs_mb"),
            ("超时 (秒)", "test_timeout_max"),
        ]:
            ctk.CTkLabel(scroll, text=label, font=font_label).grid(row=row, column=0, sticky="w", padx=8, pady=6)
            entry = ctk.CTkEntry(scroll, font=font_body, height=INPUT_HEIGHT)
            entry.grid(row=row, column=1, columnspan=2, sticky="ew", padx=6, pady=6)
            setattr(self, attr, entry)
            row += 1

        SectionTitle(scroll, "Tunnel（可选 · ChatGPT 接入）").grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=(12, 4))
        row += 1
        self.use_tunnel = ctk.CTkCheckBox(
            scroll,
            text="启用 ChatGPT Tunnel 接入（不勾选则仅本地 MCP，无需 tunnel-client）",
            font=font_body,
        )
        self.use_tunnel.grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=6)
        row += 1
        for label, attr, secret in [
            ("Tunnel ID", "tunnel_id", False),
            ("API Key", "api_key", True),
            ("Profile", "tunnel_profile", False),
            ("tunnel-client 覆盖路径", "tunnel_client_path", False),
        ]:
            ctk.CTkLabel(scroll, text=label, font=font_label).grid(row=row, column=0, sticky="w", padx=8, pady=6)
            entry = ctk.CTkEntry(
                scroll,
                font=font_body,
                height=INPUT_HEIGHT,
                show="•" if secret else None,
                placeholder_text="留空使用纳管 bin/tunnel-client/" if attr == "tunnel_client_path" else None,
            )
            setattr(self, attr, entry)
            if label.startswith("tunnel-client"):
                entry.grid(row=row, column=1, sticky="ew", padx=6, pady=6)
                ctk.CTkButton(scroll, text="浏览", width=72, command=self._browse_tunnel_client).grid(
                    row=row, column=2, padx=8, pady=6
                )
            else:
                entry.grid(row=row, column=1, columnspan=2, sticky="ew", padx=6, pady=6)
            row += 1

        ctk.CTkButton(
            scroll, text="保存配置 · 同步策略", height=BTN_HEIGHT, font=_font(SIZE_BODY, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._save_config,
        ).grid(row=row, column=0, columnspan=3, sticky="ew", padx=8, pady=16)

    def _build_ops_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        for i, (text, cmd) in enumerate(
            [
                ("刷新 Git", self._refresh_git),
                ("刷新 Session", self._refresh_sessions),
                ("结束选中 Session", self._end_selected_session),
                ("Tunnel Doctor", self._run_doctor),
                ("初始化 Tunnel", self._init_tunnel),
                ("运行安全测试", self._run_security_tests),
            ]
        ):
            ctk.CTkButton(
                toolbar, text=text, height=36, font=_font(SIZE_BODY),
                fg_color=BTN_SECONDARY, text_color=TEXT, hover_color=BTN_SECONDARY_HOVER,
                command=cmd,
            ).grid(row=0, column=i, padx=4, pady=4)

        panes = ctk.CTkFrame(parent, fg_color="transparent")
        panes.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        panes.grid_columnconfigure((0, 1), weight=1)
        panes.grid_rowconfigure((0, 1), weight=1)

        git_frame = ctk.CTkFrame(panes, fg_color=LOG_BG, corner_radius=12, border_width=1, border_color=BTN_SECONDARY)
        git_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        git_frame.grid_rowconfigure(1, weight=1)
        git_frame.grid_columnconfigure(0, weight=1)
        SectionTitle(git_frame, "Git 状态").grid(row=0, column=0, sticky="w", padx=12, pady=8)
        self.git_box = ctk.CTkTextbox(git_frame, font=_font(SIZE_LOG, family="Consolas"))
        self.git_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        sess_frame = ctk.CTkFrame(panes, fg_color=LOG_BG, corner_radius=12, border_width=1, border_color=BTN_SECONDARY)
        sess_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))
        sess_frame.grid_rowconfigure(1, weight=1)
        sess_frame.grid_columnconfigure(0, weight=1)
        SectionTitle(sess_frame, "活跃 Session").grid(row=0, column=0, sticky="w", padx=12, pady=8)
        self.session_list = ctk.CTkTextbox(sess_frame, font=_font(SIZE_LOG, family="Consolas"))
        self.session_list.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        audit_frame = ctk.CTkFrame(panes, fg_color=LOG_BG, corner_radius=12, border_width=1, border_color=BTN_SECONDARY)
        audit_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        audit_frame.grid_rowconfigure(1, weight=1)
        audit_frame.grid_columnconfigure(0, weight=1)
        SectionTitle(audit_frame, "审计摘要").grid(row=0, column=0, sticky="w", padx=12, pady=8)
        self.audit_box = ctk.CTkTextbox(audit_frame, font=_font(SIZE_LOG, family="Consolas"))
        self.audit_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

    def _build_logs_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        hdr.grid_columnconfigure(0, weight=1)
        SectionTitle(hdr, "进程与审计实时日志").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            hdr, text="清空", width=72, height=36, font=_font(SIZE_BODY),
            fg_color=BTN_SECONDARY, text_color=TEXT, hover_color=BTN_SECONDARY_HOVER,
            command=self._clear_logs,
        ).grid(row=0, column=1)
        self.log_box = ctk.CTkTextbox(
            parent, font=_font(SIZE_LOG, family="Consolas"), wrap="none",
            fg_color=LOG_BG, text_color=TEXT,
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

    def _set_textbox(self, box: ctk.CTkTextbox, text: str) -> None:
        box.delete("1.0", "end")
        box.insert("1.0", text)

    def _get_textbox(self, box: ctk.CTkTextbox) -> str:
        return box.get("1.0", "end").strip()

    def _load_form(self) -> None:
        c = self.config_data
        self.repo_root.insert(0, c.repo_root)
        self.mcp_mode.set(c.mcp_mode)
        self.max_file_bytes.insert(0, str(c.max_file_bytes))
        self.max_patch_bytes.insert(0, str(c.max_patch_bytes))
        self.audit_log.insert(0, c.audit_log)
        self.policy_rules.insert(0, c.policy_rules)
        self.sessions_file.insert(0, c.sessions_file)
        if c.allow_dirty_worktree:
            self.allow_dirty.select()
        self.rbac_default_role.insert(0, c.rbac_default_role)
        self._set_textbox(self.rbac_users, list_to_lines(c.rbac_users))
        self._set_textbox(self.protected_branches, list_to_lines(c.protected_branches))
        self._set_textbox(self.write_deny, list_to_lines(c.write_deny_patterns))
        self._set_textbox(self.execute_allow, list_to_lines(c.execute_allow))
        self.sandbox_memory.insert(0, c.sandbox_memory)
        self.sandbox_cpus.insert(0, c.sandbox_cpus)
        self.sandbox_tmpfs_mb.insert(0, str(c.sandbox_tmpfs_mb))
        self.test_timeout_max.insert(0, str(c.test_timeout_max))
        self.tunnel_id.insert(0, c.tunnel_id)
        self.api_key.insert(0, c.control_plane_api_key)
        self.tunnel_profile.insert(0, c.tunnel_profile)
        self.tunnel_client_path.insert(0, c.tunnel_client_path)
        if c.use_tunnel:
            self.use_tunnel.select()
        self._refresh_git()
        self._refresh_sessions()
        self._refresh_audit_summary()
        self._refresh_tunnel_status()
        if self._components_panel:
            self._components_panel.refresh()

    def _collect_config(self) -> AppConfig:
        return AppConfig(
            repo_root=self.repo_root.get().strip(),
            mcp_mode=self.mcp_mode.get(),
            max_file_bytes=int(self.max_file_bytes.get() or "200000"),
            max_patch_bytes=int(self.max_patch_bytes.get() or "200000"),
            allow_dirty_worktree=bool(self.allow_dirty.get()),
            audit_log=self.audit_log.get().strip(),
            policy_rules=self.policy_rules.get().strip(),
            sessions_file=self.sessions_file.get().strip(),
            protected_branches=lines_to_list(self._get_textbox(self.protected_branches)),
            write_deny_patterns=lines_to_list(self._get_textbox(self.write_deny)),
            execute_allow=lines_to_list(self._get_textbox(self.execute_allow)),
            sandbox_memory=self.sandbox_memory.get().strip() or "2g",
            sandbox_cpus=self.sandbox_cpus.get().strip() or "2",
            sandbox_tmpfs_mb=int(self.sandbox_tmpfs_mb.get() or "512"),
            test_timeout_max=int(self.test_timeout_max.get() or "300"),
            tunnel_id=self.tunnel_id.get().strip(),
            control_plane_api_key=self.api_key.get().strip(),
            tunnel_client_path=self.tunnel_client_path.get().strip(),
            tunnel_profile=self.tunnel_profile.get().strip() or "local-repo",
            rbac_default_role=self.rbac_default_role.get().strip() or "developer",
            rbac_users=lines_to_list(self._get_textbox(self.rbac_users)),
            auto_start_mcp=bool(self.auto_start_mcp.get()),
            use_tunnel=bool(self.use_tunnel.get()),
        )

    def _browse_repo(self) -> None:
        path = filedialog.askdirectory(title="选择 Git 仓库目录")
        if path:
            self.repo_root.delete(0, tk.END)
            self.repo_root.insert(0, path)

    def _browse_policy_rules(self) -> None:
        path = filedialog.askopenfilename(title="选择策略文件", filetypes=[("YAML", "*.yaml")])
        if path:
            self.policy_rules.delete(0, tk.END)
            self.policy_rules.insert(0, path)

    def _browse_sessions_file(self) -> None:
        path = filedialog.asksaveasfilename(title="Session 文件", defaultextension=".json")
        if path:
            self.sessions_file.delete(0, tk.END)
            self.sessions_file.insert(0, path)

    def _browse_tunnel_client(self) -> None:
        path = filedialog.askopenfilename(title="tunnel-client", filetypes=[("Executable", "*.exe"), ("All", "*.*")])
        if path:
            self.tunnel_client_path.delete(0, tk.END)
            self.tunnel_client_path.insert(0, path)

    def _append_log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _on_process_log(self, _source: str, line: str) -> None:
        self.after(0, lambda: self._append_log(line))

    def _clear_logs(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _save_config(self, silent: bool = False) -> AppConfig | None:
        try:
            config = self._collect_config()
        except ValueError:
            messagebox.showerror("配置错误", "数值字段格式不正确")
            return None
        errors = config.validate()
        if errors:
            messagebox.showerror("配置错误", "\n".join(errors))
            return None
        save_all(config)
        self.config_data = config
        if not silent:
            self._append_log("配置已保存（config.json / .env / config/policy.yaml）")
            messagebox.showinfo("已保存", "配置已同步")
        return config

    def _toggle_auto_start(self) -> None:
        self._save_config(silent=True)

    def _run_action(self, label: str, action) -> None:
        if self._busy:
            return
        self._busy = True
        self._append_log(f"--- {label} ---")

        def worker() -> None:
            try:
                action()
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("操作失败", str(exc)))
                self.after(0, lambda: self._append_log(f"错误: {exc}"))
            finally:
                self.after(0, lambda: setattr(self, "_busy", False))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _start_mcp(self) -> None:
        config = self._save_config(silent=True)
        if config is None:
            return

        def action() -> None:
            self.process_manager.start_mcp(config)
            self.after(0, lambda: self._append_log("MCP Server 已启动"))

        self._run_action("启动 MCP", action)

    def _start_all(self) -> None:
        config = self._save_config(silent=True)
        if config is None:
            return
        errors = config.validate_tunnel_for_start()
        if errors:
            messagebox.showerror(
                "Tunnel 配置不完整",
                "\n".join(errors) + "\n\n请在「配置」页填写 Tunnel ID 与 API Key",
            )
            self.tabview.set("配置")
            return

        def action() -> None:
            config.use_tunnel = True
            save_all(config)
            self.config_data = config
            if not self.use_tunnel.get():
                self.use_tunnel.select()
            status = self.process_manager.tunnel_status(config)
            if not status.managed:
                self.after(0, lambda: self._append_log("正在安装 tunnel-client 到项目..."))
                tag = self.process_manager.install_tunnel()
                self.after(0, lambda: self._append_log(f"tunnel-client 已纳管: {tag}"))
            self.process_manager.start_tunnel(config, init_first=True)
            self.after(0, lambda: self._append_log("Tunnel + MCP 已启动（ChatGPT 可 Scan Tools）"))
            self.after(0, self._refresh_tunnel_status)

        self._run_action("一键启动 Tunnel + MCP", action)

    def _install_tunnel(self) -> None:
        def action() -> None:
            tag = self.process_manager.install_tunnel()
            self.after(0, lambda: self._append_log(f"tunnel-client 安装完成: {tag}"))
            self.after(0, self._refresh_tunnel_status)

        self._run_action("安装 tunnel-client", action)

    def _start_tunnel_only(self) -> None:
        config = self._save_config(silent=True)
        if config is None:
            return
        errors = config.validate_tunnel_for_start()
        if errors:
            messagebox.showerror("Tunnel 配置不完整", "\n".join(errors))
            return

        def action() -> None:
            status = self.process_manager.tunnel_status(config)
            if not status.installed:
                self.process_manager.install_tunnel()
            self.process_manager.start_tunnel(config, init_first=False)
            self.after(0, lambda: self._append_log("Tunnel Client 已启动"))
            self.after(0, self._refresh_tunnel_status)

        self._run_action("启动 Tunnel", action)

    def _stop_tunnel(self) -> None:
        self.process_manager.stop(self.process_manager.tunnel)
        self._append_log("Tunnel Client 已停止")
        self._refresh_tunnel_status()

    def _restart_tunnel(self) -> None:
        config = self._save_config(silent=True)
        if config is None:
            return

        def action() -> None:
            self.process_manager.restart_tunnel(config)
            self.after(0, lambda: self._append_log("Tunnel Client 已重启"))
            self.after(0, self._refresh_tunnel_status)

        self._run_action("重启 Tunnel", action)

    def _refresh_tunnel_status(self) -> None:
        try:
            config = self._collect_config()
        except ValueError:
            config = self.config_data
        status = self.process_manager.tunnel_status(config)
        running = self.process_manager.tunnel.running
        lines = [
            f"部署位置: 本机（出站 HTTPS → OpenAI → 本地 MCP）",
            f"纳管二进制: {'是' if status.managed else '否'}",
            f"可执行文件: {status.executable}",
            f"版本: {status.version or '-'}",
            f"Profile 目录: {status.profile_dir}",
            f"当前 Profile: {config.tunnel_profile}",
            f"Profile 已初始化: {'是' if status.profile_initialized else '否'}",
            f"已注册 Profiles: {', '.join(status.profiles) or '(无)'}",
            f"进程状态: {'运行中' if running else '已停止'}",
            f"最近 Doctor: {'通过' if status.state.last_doctor_ok else '未通过/未运行'}",
        ]
        if status.state.last_error:
            lines.append(f"最近错误: {status.state.last_error[:200]}")
        self._set_textbox(self.tunnel_info_box, "\n".join(lines))

    def _open_tunnel_bin(self) -> None:
        from gui.tunnel_manager import TUNNEL_BIN_DIR
        operations.open_path(str(TUNNEL_BIN_DIR))

    def _open_tunnel_profiles(self) -> None:
        from gui.tunnel_manager import TUNNEL_PROFILE_DIR
        operations.open_path(str(TUNNEL_PROFILE_DIR))

    def _open_tunnel_data(self) -> None:
        from gui.tunnel_manager import TUNNEL_DATA_DIR
        operations.open_path(str(TUNNEL_DATA_DIR))

    def _stop_all(self) -> None:
        self.process_manager.stop_all()
        self._append_log("全部服务已停止")
        self._refresh_tunnel_status()

    def _refresh_env_check(self) -> None:
        items = operations.check_environment(self.tunnel_client_path.get().strip())
        lines = [f"[{'OK' if i['ok'] == '是' else '--' if i['ok'] == '—' else '--'}] {i['name']}: {i['detail']}" for i in items]
        self._set_textbox(self.env_box, "\n".join(lines))

    def _refresh_git(self) -> None:
        try:
            config = self._collect_config()
            text = operations.git_status(config.repo_root)
            diff = operations.git_diff(config.repo_root)
            self._set_textbox(self.git_box, text + "\n\n--- diff stat ---\n" + diff)
        except Exception as exc:
            self._set_textbox(self.git_box, str(exc))

    def _refresh_sessions(self) -> None:
        config = self._collect_config()
        sessions = operations.load_sessions(config.sessions_file)
        if not sessions:
            self._set_textbox(self.session_list, "(无活跃 Session)")
            return
        lines = []
        for s in sessions:
            lines.append(
                f"{s.get('session_id')} | user={s.get('user')} role={s.get('role', '?')} "
                f"perm={s.get('permission')} branch={s.get('branch')}"
            )
        self._set_textbox(self.session_list, "\n".join(lines))

    def _refresh_audit_summary(self) -> None:
        config = self._collect_config()
        self._set_textbox(self.audit_box, operations.read_audit_tail(config.audit_log, 40))

    def _end_selected_session(self) -> None:
        from tkinter import simpledialog

        content = self._get_textbox(self.session_list).splitlines()
        sessions = [line.split("|")[0].strip() for line in content if "|" in line]
        if not sessions:
            messagebox.showinfo("提示", "当前无活跃 Session")
            return
        session_id = simpledialog.askstring(
            "结束 Session",
            "输入要结束的 Session ID:",
            initialvalue=sessions[0],
            parent=self,
        )
        if not session_id:
            return
        config = self._save_config(silent=True)
        if config is None:
            return

        def action() -> None:
            operations.end_session(config.sessions_file, session_id.strip())
            self.after(0, self._refresh_sessions)
            self.after(0, lambda: self._append_log(f"Session 已结束: {session_id}"))

        self._run_action(f"结束 Session {session_id}", action)

    def _run_doctor(self) -> None:
        config = self._save_config(silent=True)
        if config is None:
            return
        errors = config.validate_tunnel_for_start()
        if errors:
            messagebox.showerror("Tunnel 配置不完整", "\n".join(errors))
            return

        def action() -> None:
            out = self.process_manager.run_tunnel_doctor(config)
            self.after(0, lambda: self._set_textbox(self.tunnel_doctor_box, out))
            self.after(0, lambda: self._append_log("Tunnel Doctor 完成"))
            self.after(0, self._refresh_tunnel_status)

        self._run_action("Tunnel Doctor", action)

    def _init_tunnel(self) -> None:
        config = self._save_config(silent=True)
        if config is None:
            return
        errors = config.validate_tunnel_for_start()
        if errors:
            messagebox.showerror("Tunnel 配置不完整", "\n".join(errors))
            return

        def action() -> None:
            status = self.process_manager.tunnel_status(config)
            if not status.installed:
                self.process_manager.install_tunnel()
            self.process_manager.init_tunnel(config)
            self.after(0, lambda: self._append_log("Tunnel Profile 已初始化"))
            self.after(0, self._refresh_tunnel_status)

        self._run_action("初始化 Tunnel", action)

    def _run_security_tests(self) -> None:
        def action() -> None:
            code, out = operations.run_pytest()
            self.after(0, lambda: self._set_textbox(self.audit_box, out))
            self.after(0, lambda: self._append_log(f"安全测试完成 exit={code}"))
            if code != 0:
                self.after(0, lambda: messagebox.showwarning("测试未通过", out[:2000]))

        self._run_action("运行安全测试", action)

    def _open_repo(self) -> None:
        try:
            operations.open_path(self.repo_root.get().strip())
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def _open_project(self) -> None:
        try:
            operations.open_path(str(Path(__file__).resolve().parent.parent))
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def _open_audit(self) -> None:
        try:
            operations.open_path(self.audit_log.get().strip())
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def _open_policy(self) -> None:
        try:
            path = self.policy_rules.get().strip()
            operations.open_path(path)
            if Path(path).is_file():
                import os
                if os.name == "nt":
                    os.startfile(path)  # noqa: S606
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def _tick(self) -> None:
        pm = self.process_manager
        self.mcp_status.set_running(pm.mcp.running, pm.mcp.uptime)
        self.tunnel_status.set_running(pm.tunnel.running, pm.tunnel.uptime)
        try:
            issues = local_registry.validate_config_sync(self.config_data)
            if issues:
                self.config_status.set_running(False, state_text="需同步")
            else:
                self.config_status.set_running(True, state_text="已同步")
        except Exception:
            self.config_status.set_running(False, state_text="异常")

        audit_lines, self._audit_offset = pm.tail_audit_log(self.config_data.audit_log, self._audit_offset)
        for line in audit_lines:
            self._append_log(line)
        self.after(1000, self._tick)

    def on_closing(self) -> None:
        if self.process_manager.mcp.running or self.process_manager.tunnel.running:
            if messagebox.askyesno("退出", "有服务正在运行，是否停止并退出？"):
                self.process_manager.stop_all()
                self.destroy()
        else:
            self.destroy()


def main() -> None:
    app = MCPControlApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
