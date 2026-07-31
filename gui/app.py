"""Local Repo MCP 控制面板。"""

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
SIZE_LOG = 15
INPUT_HEIGHT = 38
BTN_HEIGHT = 40
BTN_HEIGHT_LG = 48


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

        self.title_label = ctk.CTkLabel(
            self, text=label, font=_font(SIZE_SECTION, "bold"), text_color=TEXT
        )
        self.title_label.grid(row=0, column=1, sticky="w", pady=14)

        self.state = ctk.CTkLabel(self, text="已停止", font=_font(SIZE_BODY), text_color=MUTED)
        self.state.grid(row=0, column=2, padx=(0, 8), pady=14)

        self.uptime = ctk.CTkLabel(self, text="", font=_font(SIZE_BODY), text_color=MUTED)
        self.uptime.grid(row=0, column=3, padx=(0, 14), pady=14)

    def set_running(self, running: bool, uptime: str = "") -> None:
        if running:
            self.dot.configure(text_color=SUCCESS)
            self.state.configure(text="运行中", text_color=SUCCESS)
            self.uptime.configure(text=uptime)
        else:
            self.dot.configure(text_color=MUTED)
            self.state.configure(text="已停止", text_color=MUTED)
            self.uptime.configure(text="")


class SectionTitle(ctk.CTkLabel):
    def __init__(self, master: ctk.CTkBaseClass, text: str) -> None:
        super().__init__(
            master,
            text=text,
            font=_font(SIZE_SECTION, "bold"),
            text_color=MUTED,
            anchor="w",
        )


class MCPControlApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Local Repo MCP")
        self.geometry("1100x820")
        self.minsize(960, 700)
        self.configure(fg_color=BG_APP)

        self.config_data = load_config()
        self.process_manager = ProcessManager(on_log=self._on_process_log)
        self._audit_offset = 0
        self._log_buffer: list[str] = []
        self._busy = False

        self._build_layout()
        self._load_form()
        self._tick()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=2, minsize=360)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(18, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Local Repo MCP",
            font=_font(SIZE_TITLE, "bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Secure MCP Tunnel 控制面板",
            font=_font(SIZE_SUBTITLE),
            text_color=MUTED,
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        status_bar = ctk.CTkFrame(self, fg_color="transparent")
        status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 10))
        status_bar.grid_columnconfigure(0, weight=1)
        status_bar.grid_columnconfigure(1, weight=1)

        self.mcp_status = StatusBadge(status_bar, "MCP Server")
        self.mcp_status.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.tunnel_status = StatusBadge(status_bar, "Tunnel Client")
        self.tunnel_status.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        left = ctk.CTkScrollableFrame(
            self, fg_color=BG_CARD, corner_radius=16, border_width=1, border_color=BTN_SECONDARY
        )
        left.grid(row=2, column=0, sticky="nsew", padx=(20, 10), pady=(0, 20))
        left.grid_columnconfigure(1, weight=1)

        right = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=16, border_width=1, border_color=BTN_SECONDARY
        )
        right.grid(row=2, column=1, sticky="nsew", padx=(10, 20), pady=(0, 20))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        font_body = _font(SIZE_BODY)
        font_label = _font(SIZE_BODY)
        font_btn = _font(SIZE_BODY)
        font_btn_lg = _font(SIZE_BTN_LG, "bold")
        font_log = _font(SIZE_LOG, family="Consolas")
        font_footer = _font(SIZE_FOOTER)
        font_section = _font(SIZE_SECTION, "bold")

        row = 0
        SectionTitle(left, "仓库设置").grid(row=row, column=0, columnspan=3, sticky="w", padx=16, pady=(16, 8))
        row += 1

        ctk.CTkLabel(left, text="仓库路径", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.repo_root = ctk.CTkEntry(left, placeholder_text="选择本地 Git 仓库", font=font_body, height=INPUT_HEIGHT)
        self.repo_root.grid(row=row, column=1, sticky="ew", padx=6, pady=8)
        ctk.CTkButton(
            left, text="浏览", width=80, height=INPUT_HEIGHT, font=font_btn, command=self._browse_repo
        ).grid(row=row, column=2, padx=(0, 16), pady=8)
        row += 1

        ctk.CTkLabel(left, text="运行模式", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.mcp_mode = ctk.CTkComboBox(
            left, values=list(MCP_MODES), state="readonly", font=font_body, dropdown_font=font_body, height=INPUT_HEIGHT
        )
        self.mcp_mode.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        SectionTitle(left, "安全与审计").grid(row=row, column=0, columnspan=3, sticky="w", padx=16, pady=(16, 8))
        row += 1

        ctk.CTkLabel(left, text="最大文件 (B)", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.max_file_bytes = ctk.CTkEntry(left, font=font_body, height=INPUT_HEIGHT)
        self.max_file_bytes.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        ctk.CTkLabel(left, text="最大 Patch (B)", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.max_patch_bytes = ctk.CTkEntry(left, font=font_body, height=INPUT_HEIGHT)
        self.max_patch_bytes.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        ctk.CTkLabel(left, text="审计日志", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.audit_log = ctk.CTkEntry(left, font=font_body, height=INPUT_HEIGHT)
        self.audit_log.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        ctk.CTkLabel(left, text="策略文件", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.policy_rules = ctk.CTkEntry(left, font=font_body, height=INPUT_HEIGHT)
        self.policy_rules.grid(row=row, column=1, sticky="ew", padx=6, pady=8)
        ctk.CTkButton(
            left, text="浏览", width=80, height=INPUT_HEIGHT, font=font_btn, command=self._browse_policy_rules
        ).grid(row=row, column=2, padx=(0, 16), pady=8)
        row += 1

        ctk.CTkLabel(left, text="Session 文件", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.sessions_file = ctk.CTkEntry(left, font=font_body, height=INPUT_HEIGHT)
        self.sessions_file.grid(row=row, column=1, sticky="ew", padx=6, pady=8)
        ctk.CTkButton(
            left, text="浏览", width=80, height=INPUT_HEIGHT, font=font_btn, command=self._browse_sessions_file
        ).grid(row=row, column=2, padx=(0, 16), pady=8)
        row += 1

        self.allow_dirty = ctk.CTkCheckBox(left, text="允许 dirty worktree 时 apply patch", font=font_body)
        self.allow_dirty.grid(row=row, column=0, columnspan=3, sticky="w", padx=16, pady=(4, 8))
        row += 1

        SectionTitle(left, "Git 分支保护").grid(row=row, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 4))
        row += 1

        ctk.CTkLabel(left, text="受保护分支", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="nw", padx=16, pady=8)
        self.protected_branches = ctk.CTkTextbox(left, font=font_body, height=72)
        self.protected_branches.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        SectionTitle(left, "写入策略 (deny)").grid(row=row, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 4))
        row += 1

        ctk.CTkLabel(left, text="禁止写入", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="nw", padx=16, pady=8)
        self.write_deny = ctk.CTkTextbox(left, font=font_body, height=96)
        self.write_deny.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        SectionTitle(left, "测试命令白名单").grid(row=row, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 4))
        row += 1

        ctk.CTkLabel(left, text="允许执行", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="nw", padx=16, pady=8)
        self.execute_allow = ctk.CTkTextbox(left, font=font_body, height=96)
        self.execute_allow.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        SectionTitle(left, "Docker 沙箱").grid(row=row, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 8))
        row += 1

        ctk.CTkLabel(left, text="内存限制", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.sandbox_memory = ctk.CTkEntry(left, placeholder_text="2g", font=font_body, height=INPUT_HEIGHT)
        self.sandbox_memory.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        ctk.CTkLabel(left, text="CPU 限制", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.sandbox_cpus = ctk.CTkEntry(left, placeholder_text="2", font=font_body, height=INPUT_HEIGHT)
        self.sandbox_cpus.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        ctk.CTkLabel(left, text="tmpfs (MB)", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.sandbox_tmpfs_mb = ctk.CTkEntry(left, font=font_body, height=INPUT_HEIGHT)
        self.sandbox_tmpfs_mb.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        ctk.CTkLabel(left, text="测试超时 (秒)", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.test_timeout_max = ctk.CTkEntry(left, font=font_body, height=INPUT_HEIGHT)
        self.test_timeout_max.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        SectionTitle(left, "Tunnel 设置").grid(row=row, column=0, columnspan=3, sticky="w", padx=16, pady=(16, 8))
        row += 1

        ctk.CTkLabel(left, text="Tunnel ID", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.tunnel_id = ctk.CTkEntry(left, placeholder_text="tunnel_xxxxxxxx", font=font_body, height=INPUT_HEIGHT)
        self.tunnel_id.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        ctk.CTkLabel(left, text="API Key", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.api_key = ctk.CTkEntry(left, placeholder_text="sk-...", show="•", font=font_body, height=INPUT_HEIGHT)
        self.api_key.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        ctk.CTkLabel(left, text="Profile", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.tunnel_profile = ctk.CTkEntry(left, font=font_body, height=INPUT_HEIGHT)
        self.tunnel_profile.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(6, 16), pady=8)
        row += 1

        ctk.CTkLabel(left, text="tunnel-client", font=font_label, text_color=TEXT).grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.tunnel_client_path = ctk.CTkEntry(left, placeholder_text="留空则使用 PATH", font=font_body, height=INPUT_HEIGHT)
        self.tunnel_client_path.grid(row=row, column=1, sticky="ew", padx=6, pady=8)
        ctk.CTkButton(
            left, text="浏览", width=80, height=INPUT_HEIGHT, font=font_btn, command=self._browse_tunnel_client
        ).grid(row=row, column=2, padx=(0, 16), pady=8)
        row += 1

        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.grid(row=row, column=0, columnspan=3, sticky="ew", padx=12, pady=(18, 16))
        actions.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            actions,
            text="保存配置 · 同步策略",
            font=font_btn,
            height=BTN_HEIGHT,
            command=self._save_config,
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=6)
        ctk.CTkButton(
            actions,
            text="启动 MCP",
            font=font_btn,
            height=BTN_HEIGHT,
            fg_color=BTN_SECONDARY,
            text_color=TEXT,
            hover_color=BTN_SECONDARY_HOVER,
            command=self._start_mcp,
        ).grid(row=0, column=1, sticky="ew", padx=4, pady=6)

        ctk.CTkButton(
            actions,
            text="启动 Tunnel",
            font=font_btn,
            height=BTN_HEIGHT,
            fg_color=BTN_SECONDARY,
            text_color=TEXT,
            hover_color=BTN_SECONDARY_HOVER,
            command=self._start_tunnel,
        ).grid(row=1, column=0, sticky="ew", padx=4, pady=6)

        ctk.CTkButton(
            actions,
            text="全部停止",
            font=font_btn,
            height=BTN_HEIGHT,
            fg_color=DANGER,
            hover_color="#DC2626",
            command=self._stop_all,
        ).grid(row=1, column=1, sticky="ew", padx=4, pady=6)

        ctk.CTkButton(
            actions,
            text="▶  一键启动全部",
            height=BTN_HEIGHT_LG,
            font=font_btn_lg,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._start_all,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(12, 0))

        log_header = ctk.CTkFrame(right, fg_color="transparent")
        log_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        log_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_header, text="运行监控", font=font_section, text_color=TEXT
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            log_header,
            text="清空",
            width=72,
            height=36,
            font=font_btn,
            fg_color=BTN_SECONDARY,
            text_color=TEXT,
            hover_color=BTN_SECONDARY_HOVER,
            command=self._clear_logs,
        ).grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(
            right,
            font=font_log,
            wrap="none",
            activate_scrollbars=True,
            fg_color=LOG_BG,
            text_color=TEXT,
            border_color=BTN_SECONDARY,
            border_width=1,
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.log_box.configure(state="disabled")

        footer = ctk.CTkLabel(
            self,
            text="默认 read 模式 · 写入/测试需切换 MCP_MODE · git push 永不开放",
            font=font_footer,
            text_color=MUTED,
        )
        footer.grid(row=3, column=0, columnspan=2, sticky="w", padx=22, pady=(0, 12))

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
        )

    def _browse_repo(self) -> None:
        path = filedialog.askdirectory(title="选择 Git 仓库目录")
        if path:
            self.repo_root.delete(0, tk.END)
            self.repo_root.insert(0, path)

    def _browse_policy_rules(self) -> None:
        path = filedialog.asksaveasfilename(
            title="选择或新建策略文件",
            defaultextension=".yaml",
            filetypes=[("YAML", "*.yaml"), ("All files", "*.*")],
        )
        if path:
            self.policy_rules.delete(0, tk.END)
            self.policy_rules.insert(0, path)

    def _browse_sessions_file(self) -> None:
        path = filedialog.asksaveasfilename(
            title="选择 Session 存储文件",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.sessions_file.delete(0, tk.END)
            self.sessions_file.insert(0, path)

    def _browse_tunnel_client(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 tunnel-client 可执行文件",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.tunnel_client_path.delete(0, tk.END)
            self.tunnel_client_path.insert(0, path)

    def _append_log(self, text: str) -> None:
        self._log_buffer.append(text)
        if len(self._log_buffer) > 3000:
            self._log_buffer = self._log_buffer[-3000:]
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _on_process_log(self, _source: str, line: str) -> None:
        self.after(0, lambda: self._append_log(line))

    def _clear_logs(self) -> None:
        self._log_buffer.clear()
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
            self._append_log("配置已保存（config.json / .env / rules.yaml）")
            messagebox.showinfo("已保存", "配置已写入 config.json、.env 与策略文件")
        return config

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

        self._run_action("启动 MCP Server", action)

    def _start_tunnel(self) -> None:
        config = self._save_config(silent=True)
        if config is None:
            return
        errors = config.validate_tunnel()
        if errors:
            messagebox.showerror("Tunnel 配置不完整", "\n".join(errors))
            return

        def action() -> None:
            self.process_manager.start_tunnel(config)
            self.after(0, lambda: self._append_log("Tunnel Client 已启动"))

        self._run_action("启动 Tunnel Client", action)

    def _start_all(self) -> None:
        config = self._save_config(silent=True)
        if config is None:
            return
        errors = config.validate_tunnel()
        if errors:
            messagebox.showerror("配置不完整", "\n".join(errors))
            return

        def action() -> None:
            self.process_manager.start_tunnel(config)
            self.after(0, lambda: self._append_log("Tunnel 已启动（将自动拉起 MCP Server）"))

        self._run_action("一键启动全部", action)

    def _stop_all(self) -> None:
        self.process_manager.stop_all()
        self._append_log("全部服务已停止")

    def _tick(self) -> None:
        pm = self.process_manager
        self.mcp_status.set_running(pm.mcp.running, pm.mcp.uptime)
        self.tunnel_status.set_running(pm.tunnel.running, pm.tunnel.uptime)

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
