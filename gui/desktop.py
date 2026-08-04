from __future__ import annotations

from pathlib import Path
from tkinter import PhotoImage, TclError, filedialog, messagebox

import customtkinter as ctk

from gui import log_workspace
from gui.app import (
    ASSETS,
    PAGE_SUBTITLES,
    LocalRepoMCPApp as BaseApplication,
)
from gui.config import load_config
from gui.connection_state import ConnectionState, configuration_fingerprint
from gui.connection import run_connection_test
from gui.i18n import tr
from gui.processes import ProcessManager
from gui.theme import COLORS, FONT_BODY
from gui.tunnel import TunnelManager
from repo.worktree import initialize_worktree, inspect_worktree


class LocalRepoMCPApp(BaseApplication):
    """Single desktop composition root."""

    def __init__(self) -> None:
        self.config_data = load_config()
        ctk.set_appearance_mode(self.config_data.appearance)
        ctk.CTk.__init__(self)

        self.title("Local Repo MCP")
        self._app_icons = {
            size: PhotoImage(file=str(ASSETS / f"app-icon-{size}.png"))
            for size in (16, 32, 40, 64)
        }
        self.iconphoto(True, *(self._app_icons[size] for size in (16, 32, 64)))
        try:
            self.iconbitmap(default=str(ASSETS / "app-icon.ico"))
        except TclError:
            pass
        self.geometry("1280x820")
        self.minsize(1060, 700)
        self.configure(fg_color=COLORS["bg"])

        self.processes = ProcessManager()
        self.tunnel = TunnelManager(self.processes)
        self.connection_state = ConnectionState()
        self._connection_attempt = False
        self.current_page = "home"
        self.busy = False
        self.last_test: dict | None = None
        self.api_key_visible = False
        self.token_visible = False
        self.section_state = {
            "home_http": True,
            "home_advanced": False,
            "server_check": False,
            "server_client": False,
            "chatgpt_auth": False,
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

    def _show_page(self, page: str) -> None:
        log_workspace.cancel(self)
        self.current_page = page
        for key, button in self.nav_buttons.items():
            active = key == page
            button.configure(
                fg_color=COLORS["sidebar_active"] if active else "transparent",
                text_color=COLORS["text"],
                font=ctk.CTkFont(
                    size=FONT_BODY,
                    weight="bold" if active else "normal",
                ),
            )
        self.page_title.configure(text=self.t(page))
        self.page_subtitle.configure(text=self.t(PAGE_SUBTITLES[page]))
        for child in self.page_container.winfo_children():
            child.destroy()
        {
            "home": self._build_home,
            "server": self._build_server,
            "chatgpt": self._build_chatgpt,
            "logs": self._build_logs_center,
            "about": self._build_about,
        }[page]()

    def _repo_message(self, zh: str, en: str) -> str:
        return zh if self.config_data.language == "zh" else en

    @staticmethod
    def _resolved_text(path: str) -> str:
        return str(Path(path).expanduser().resolve()) if path.strip() else ""

    def _fingerprint_for_config(self, config) -> tuple[str, ...]:
        return configuration_fingerprint(
            repository=self._resolved_text(config.repo_root),
            mode=config.mcp_mode,
            transport=config.transport,
            endpoint=(
                config.endpoint_url()
                if config.transport == "streamable-http"
                else ""
            ),
            token=(
                config.http_auth_token
                if config.transport == "streamable-http"
                else ""
            ),
        )

    def _current_connection_fingerprint(self) -> tuple[str, ...] | None:
        config = BaseApplication._collect_config(self, quiet=True)
        return None if config is None else self._fingerprint_for_config(config)

    def connection_verified(self) -> bool:
        fingerprint = self._current_connection_fingerprint()
        return (
            fingerprint is not None
            and self.connection_state.matches(fingerprint)
        )

    def connection_action_text(self) -> str:
        return self.t("reconnect") if self.connection_verified() else self.t("connect")

    def _primary_button(self, parent, text, command, *, danger=False):
        if text == self.t("connect"):
            text = self.connection_action_text()
        return super()._primary_button(parent, text, command, danger=danger)

    def _secondary_button(self, parent, text, command):
        if text == self.t("connect"):
            text = self.connection_action_text()
        return super()._secondary_button(parent, text, command)

    def _ensure_git_repository(self, *, prompt: bool) -> bool:
        raw = self.repo_var.get().strip()
        if not raw:
            return True
        check = inspect_worktree(raw)
        if check.ready:
            assert check.root is not None
            if check.is_root:
                return True
            if not prompt:
                return False
            use_root = messagebox.askyesno(
                self._repo_message(
                    "使用 Git 工作区根目录",
                    "Use Git working-tree root",
                ),
                self._repo_message(
                    "所选目录位于现有 Git 工作区内部：\n\n{path}\n\n"
                    "Local Repo MCP 必须以完整 Git 工作区作为安全边界。"
                    "是否切换到工作区根目录？\n\n{root}",
                    "The selected folder is inside an existing Git working tree:\n\n"
                    "{path}\n\nLocal Repo MCP requires the complete Git working "
                    "tree as its security boundary. Use this root instead?\n\n{root}",
                ).format(path=check.path, root=check.root),
            )
            if not use_root:
                return False
            self.repo_var.set(str(check.root))
            self.connection_state.invalidate()
            self._status(
                self._repo_message(
                    "已切换到 Git 工作区根目录",
                    "Switched to Git working-tree root",
                ),
                "success",
            )
            return True
        if check.status in {"missing", "not_directory"}:
            return True
        if check.status == "git_missing":
            if prompt:
                messagebox.showerror(self.t("error"), self.t("git_required"))
            return False
        if check.status == "error":
            if prompt:
                messagebox.showerror(
                    self.t("error"),
                    check.detail
                    or self._repo_message(
                        "Git 仓库检查失败。",
                        "Git repository check failed.",
                    ),
                )
            return False
        if not prompt:
            return False

        if not messagebox.askyesno(
            self._repo_message("初始化 Git 仓库", "Initialize Git repository"),
            self._repo_message(
                "所选目录还不是 Git 工作区：\n\n{path}\n\n"
                "是否在该目录执行 git init？此操作只会创建 .git 元数据，"
                "不会提交文件、添加远程仓库或修改现有项目内容。",
                "The selected folder is not a Git working tree:\n\n{path}\n\n"
                "Run git init in this folder? This only creates .git metadata; "
                "it does not commit files, add a remote, or modify project content.",
            ).format(path=raw),
        ):
            return False
        try:
            initialized = initialize_worktree(raw)
        except Exception as exc:
            messagebox.showerror(
                self.t("error"),
                self._repo_message(
                    "Git 初始化失败：{error}",
                    "Git initialization failed: {error}",
                ).format(error=str(exc)),
            )
            return False
        self.repo_var.set(str(initialized.root or initialized.path))
        self.connection_state.invalidate()
        self._status(
            self._repo_message(
                "Git 仓库初始化成功",
                "Git repository initialized",
            ),
            "success",
        )
        return True

    def _collect_config(self, *, quiet: bool = False):
        if not quiet and not self._ensure_git_repository(prompt=True):
            return None
        return BaseApplication._collect_config(self, quiet=quiet)

    def _browse_repo(self) -> None:
        previous = self.repo_var.get().strip()
        path = filedialog.askdirectory(initialdir=previous or str(Path.cwd()))
        if not path:
            return
        self.repo_var.set(path)
        if not self._ensure_git_repository(prompt=True):
            self.repo_var.set(previous)
            return
        if self.repo_var.get().strip() != previous:
            self.connection_state.invalidate()
        self._show_page("home")

    def _git_branch(self) -> str:
        raw = self.repo_var.get().strip()
        if not raw:
            return "—"
        check = inspect_worktree(raw)
        if check.status == "not_git":
            return self._repo_message("未初始化 Git", "Git not initialized")
        return check.branch if check.ready else "—"

    def _run_smoke_test(self) -> None:
        config = self._save()
        if config is None:
            return
        if (
            config.transport == "streamable-http"
            and not self.processes.mcp.running
        ):
            messagebox.showerror(
                self.t("error"),
                self.t("start_http_first"),
            )
            return
        fingerprint = self._fingerprint_for_config(config)
        self._connection_attempt = True

        def success(value):
            self._connection_attempt = False
            self.last_test = value
            self.connection_state.mark_verified(fingerprint, value)
            self._status(self.t("connected"), "success")
            self._show_page("server")

        self._background(
            lambda: run_connection_test(
                config,
                log_callback=self.processes.mcp.append_log,
            ),
            on_success=success,
        )

    def _failed(self, error: str) -> None:
        if self._connection_attempt:
            self.connection_state.mark_failed(error)
            self._connection_attempt = False
        super()._failed(error)

    def _transport_changed(self, value: str) -> None:
        self.connection_state.invalidate()
        super()._transport_changed(value)

    def _start_http(self) -> None:
        self.connection_state.invalidate()
        super()._start_http()

    def _stop_http(self) -> None:
        self.connection_state.invalidate()
        super()._stop_http()


def main() -> None:
    LocalRepoMCPApp().mainloop()


if __name__ == "__main__":
    main()
