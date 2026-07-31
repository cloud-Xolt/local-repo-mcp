"""本地组件面板 — 统一纳管视图。"""

from __future__ import annotations

import os
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from gui import local_registry, operations
from gui.config import AppConfig

TEXT = "#334155"
MUTED = "#64748B"
LOG_BG = "#F8FAFC"
BTN_SECONDARY = "#E2E8F0"
BTN_SECONDARY_HOVER = "#CBD5E1"
ACCENT = "#2563EB"
ACCENT_HOVER = "#1D4ED8"
SUCCESS = "#16A34A"


class LocalComponentsPanel:
    def __init__(
        self,
        parent: ctk.CTkFrame,
        app: object,
        font_body: ctk.CTkFont,
        font_section: ctk.CTkFont,
        font_log: ctk.CTkFont,
    ) -> None:
        self.app = app
        self._font_body = font_body
        self._font_section = font_section
        self._font_log = font_log

        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            hdr,
            text="本地侧组件纳管 · Tunnel 可选 · 纯 MCP 模式无需 tunnel-client",
            font=font_section,
            text_color=MUTED,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            hdr, text="刷新", width=80, height=32, font=font_body,
            fg_color=BTN_SECONDARY, text_color=TEXT, hover_color=BTN_SECONDARY_HOVER,
            command=self.refresh,
        ).grid(row=0, column=1, padx=4)
        ctk.CTkButton(
            hdr, text="同步全部配置", width=120, height=32, font=font_body,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._sync_all,
        ).grid(row=0, column=2, padx=4)
        ctk.CTkButton(
            hdr, text="修复本地目录", width=120, height=32, font=font_body,
            fg_color=BTN_SECONDARY, text_color=TEXT, hover_color=BTN_SECONDARY_HOVER,
            command=self._ensure_layout,
        ).grid(row=0, column=3, padx=4)

        self.sync_label = ctk.CTkLabel(hdr, text="", font=font_body, text_color=MUTED)
        self.sync_label.grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))

        scroll = ctk.CTkScrollableFrame(parent, fg_color=LOG_BG, corner_radius=12)
        scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        scroll.grid_columnconfigure(0, weight=3)
        scroll.grid_columnconfigure(1, weight=1)
        scroll.grid_columnconfigure(2, weight=1)
        scroll.grid_columnconfigure(3, weight=2)
        self.scroll = scroll
        self._header_row = 1

        ctk.CTkLabel(scroll, text="组件", font=font_section, text_color=TEXT).grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ctk.CTkLabel(scroll, text="类型", font=font_section, text_color=TEXT).grid(row=0, column=1, sticky="w", padx=8, pady=8)
        ctk.CTkLabel(scroll, text="状态", font=font_section, text_color=TEXT).grid(row=0, column=2, sticky="w", padx=8, pady=8)
        ctk.CTkLabel(scroll, text="操作", font=font_section, text_color=TEXT).grid(row=0, column=3, sticky="w", padx=8, pady=8)

    def refresh(self) -> None:
        config: AppConfig = self.app._collect_config()
        pm = self.app.process_manager
        statuses = local_registry.scan_components(config, pm)
        issues = local_registry.validate_config_sync(config)

        for w in self.scroll.winfo_children():
            info = w.grid_info()
            if info and int(info.get("row", 0)) >= self._header_row:
                w.destroy()

        if issues:
            self.sync_label.configure(
                text=f"配置同步: 需修复 — {'; '.join(issues[:3])}",
                text_color="#DC2626",
            )
        else:
            self.sync_label.configure(
                text="配置同步: 正常 (config.json ↔ .env ↔ policy.yaml)",
                text_color=SUCCESS,
            )

        row = self._header_row
        for st in statuses:
            name_color = TEXT if st.ok else "#DC2626"
            ctk.CTkLabel(
                self.scroll, text=st.component.name, font=self._font_body, text_color=name_color, anchor="w"
            ).grid(row=row, column=0, sticky="w", padx=8, pady=6)
            ctk.CTkLabel(
                self.scroll, text=st.component.category, font=self._font_body, text_color=MUTED
            ).grid(row=row, column=1, sticky="w", padx=8, pady=6)
            ctk.CTkLabel(
                self.scroll, text=st.status, font=self._font_body, text_color=TEXT
            ).grid(row=row, column=2, sticky="w", padx=8, pady=6)

            actions = ctk.CTkFrame(self.scroll, fg_color="transparent")
            actions.grid(row=row, column=3, sticky="ew", padx=4, pady=4)
            for i, action in enumerate(st.actions):
                ctk.CTkButton(
                    actions,
                    text=action,
                    width=72,
                    height=28,
                    font=self._font_body,
                    fg_color=BTN_SECONDARY,
                    text_color=TEXT,
                    hover_color=BTN_SECONDARY_HOVER,
                    command=lambda a=action, s=st: self._dispatch(a, s),
                ).grid(row=0, column=i, padx=2)

            ctk.CTkLabel(
                self.scroll,
                text=st.detail[:120],
                font=self._font_log,
                text_color=MUTED,
                anchor="w",
            ).grid(row=row + 1, column=0, columnspan=4, sticky="w", padx=8, pady=(0, 4))
            row += 2

    def _dispatch(self, action: str, st) -> None:
        comp_id = st.component.component_id
        if action == "打开":
            self._open(st)
        elif action == "启动":
            self._start_component(comp_id)
        elif action == "停止":
            self._stop_component(comp_id)
        elif action == "安装":
            self.app._install_tunnel()
        elif action == "Doctor":
            self.app._run_doctor()
        elif action == "同步全部配置":
            self._sync_all()
        elif action == "安装依赖":
            self._install_deps()
        elif action == "刷新":
            self.refresh()
        elif action == "清空":
            self._clear_audit()

    def _open(self, st) -> None:
        config: AppConfig = self.app._collect_config()
        path = st.component.path
        if st.component.component_id == "target_repo":
            path = Path(config.repo_root)
        elif st.component.component_id == "policy_yaml":
            path = Path(config.policy_rules)
        elif st.component.component_id == "sessions":
            path = Path(config.sessions_file)
        elif st.component.component_id == "audit_log":
            path = Path(config.audit_log)
        try:
            if path.is_file() and os.name == "nt":
                os.startfile(str(path))  # noqa: S606
            else:
                operations.open_path(str(path if path.is_dir() else path.parent))
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def _start_component(self, comp_id: str) -> None:
        if comp_id == "mcp_server":
            self.app._start_mcp()
        elif comp_id == "tunnel_client":
            self.app._start_tunnel_only()

    def _stop_component(self, comp_id: str) -> None:
        pm = self.app.process_manager
        if comp_id == "mcp_server":
            pm.stop(pm.mcp)
            self.app._append_log("MCP Server 已停止")
        elif comp_id == "tunnel_client":
            self.app._stop_tunnel()
        self.after_refresh()

    def after_refresh(self) -> None:
        self.app.after(500, self.refresh)

    def _sync_all(self) -> None:
        config = self.app._save_config(silent=True)
        if config is None:
            return
        local_registry.sync_all_configs(config)
        self.app.config_data = config
        self.app._append_log("已同步 config.json / .env / policy.yaml")
        self.refresh()

    def _ensure_layout(self) -> None:
        config = self.app._save_config(silent=True)
        if config:
            local_registry.ensure_local_layout(config)
            local_registry.sync_all_configs(config)
            self.app._append_log("本地目录与配置已修复")
            self.refresh()

    def _install_deps(self) -> None:
        def action() -> None:
            local_registry.install_venv_dependencies(
                on_log=lambda m: self.app.after(0, lambda msg=m: self.app._append_log(msg))
            )
            self.app.after(0, self.refresh)

        self.app._run_action("安装 Python 依赖", action)

    def _clear_audit(self) -> None:
        config: AppConfig = self.app._collect_config()
        path = Path(config.audit_log)
        if path.exists() and messagebox.askyesno("确认", f"清空审计日志？\n{path}"):
            path.write_text("", encoding="utf-8")
            self.app._append_log("审计日志已清空")
            self.refresh()
