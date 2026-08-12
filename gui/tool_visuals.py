from __future__ import annotations

from dataclasses import dataclass
from tkinter import Canvas

import customtkinter as ctk

from gui.colors import resolve_color
from gui.theme import COLORS, FONT_BODY, FONT_SMALL


@dataclass(frozen=True)
class ToolVisual:
    name: str
    title_zh: str
    title_en: str
    description_zh: str
    description_en: str
    color: str
    icon: str


TOOL_VISUALS = (
    ToolVisual("repo_list_files", "列出仓库文件", "List repository files", "查看仓库中的文件与目录结构", "Inspect repository files and directories", "#5B6EE1", "list"),
    ToolVisual("repo_read_file", "读取文件", "Read file", "读取仓库中的 UTF-8 文本文件", "Read UTF-8 text from the repository", "#2E8BC0", "document"),
    ToolVisual("repo_search_code", "搜索代码", "Search code", "执行受限的固定字符串检索", "Run bounded fixed-string search", "#8B5CF6", "search"),
    ToolVisual("repo_git_status", "查看 Git 状态", "Read Git status", "查看经过敏感路径过滤的工作区状态", "Read filtered worktree status", "#29966F", "branch"),
    ToolVisual("repo_git_diff", "查看 Git 差异", "Read Git diff", "查看受限且经过过滤的代码差异", "Read bounded and filtered diffs", "#C47A22", "diff"),
    ToolVisual("repo_apply_patch", "应用代码修改", "Apply code changes", "应用经过校验的统一文本修改", "Apply validated unified text changes", "#D65A45", "patch"),
    ToolVisual("repo_git_commit", "提交本地更改", "Commit local changes", "在启用时创建本地 Git commit", "Create a local Git commit when enabled", "#0F766E", "commit"),
    ToolVisual("repo_run_test", "运行验证命令", "Run verification commands", "运行白名单 test/build/lint/check 命令", "Run allowlisted test/build/lint/check commands", "#B54AA5", "test"),
)
VISUAL_BY_NAME = {item.name: item for item in TOOL_VISUALS}


class ToolIcon(Canvas):
    """DPI-friendly vector icon rendered with Tk canvas primitives."""

    def __init__(self, master, visual: ToolVisual, size: int = 42) -> None:
        background = resolve_color(COLORS["surface_alt"])
        super().__init__(
            master,
            width=size,
            height=size,
            background=background,
            highlightthickness=0,
            borderwidth=0,
        )
        self.visual = visual
        self.size = size
        self._draw()

    def _line(self, *coords: float, width: int = 2) -> None:
        self.create_line(
            *coords,
            fill=self.visual.color,
            width=width,
            capstyle="round",
            joinstyle="round",
        )

    def _rect(self, *coords: float, width: int = 2) -> None:
        self.create_rectangle(*coords, outline=self.visual.color, width=width)

    def _draw(self) -> None:
        s = self.size
        kind = self.visual.icon
        if kind == "list":
            for y in (13, 21, 29):
                self.create_oval(10, y - 2, 14, y + 2, fill=self.visual.color, outline="")
                self._line(18, y, 32, y)
        elif kind == "document":
            self._rect(12, 8, 30, 34)
            self._line(24, 8, 30, 14, 24, 14, 24, 8)
            self._line(16, 20, 26, 20)
            self._line(16, 26, 26, 26)
        elif kind == "search":
            self.create_oval(10, 9, 28, 27, outline=self.visual.color, width=2)
            self._line(26, 25, 34, 33, width=3)
        elif kind == "branch":
            self.create_oval(10, 8, 16, 14, outline=self.visual.color, width=2)
            self.create_oval(26, 17, 32, 23, outline=self.visual.color, width=2)
            self.create_oval(10, 28, 16, 34, outline=self.visual.color, width=2)
            self._line(13, 14, 13, 28)
            self._line(13, 20, 26, 20)
        elif kind == "diff":
            self._line(12, 12, 12, 30)
            self._line(8, 16, 12, 12, 16, 16)
            self._line(30, 12, 30, 30)
            self._line(26, 26, 30, 30, 34, 26)
        elif kind == "patch":
            self._rect(10, 10, 32, 32)
            self._line(21, 15, 21, 27)
            self._line(15, 21, 27, 21)
        elif kind == "commit":
            self.create_oval(14, 10, 28, 24, outline=self.visual.color, width=2)
            self._line(21, 24, 21, 34, width=3)
            self._line(16, 34, 26, 34)
        elif kind == "test":
            self._line(16, 9, 26, 9)
            self._line(18, 9, 18, 18, 11, 31)
            self._line(24, 9, 24, 18, 31, 31)
            self._line(11, 31, 31, 31)
            self._line(16, 25, 26, 25)


def build_tool_grid(app, parent, tools: list[str] | None = None) -> None:
    visible = set(tools or VISUAL_BY_NAME)
    specs = [item for item in TOOL_VISUALS if item.name in visible]
    language = app.config_data.language
    for index, visual in enumerate(specs):
        row, column = divmod(index, 2)
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["surface_alt"],
            corner_radius=11,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(0, 6) if column == 0 else (6, 0),
            pady=6,
        )
        parent.grid_columnconfigure(column, weight=1, uniform="tool-cards")
        icon_wrap = ctk.CTkFrame(
            card,
            width=48,
            height=48,
            fg_color="transparent",
            corner_radius=12,
        )
        icon_wrap.grid(row=0, column=0, rowspan=2, padx=13, pady=13)
        icon_wrap.grid_propagate(False)
        ToolIcon(icon_wrap, visual, 42).place(relx=0.5, rely=0.5, anchor="center")
        title = visual.title_zh if language == "zh" else visual.title_en
        description = (
            visual.description_zh if language == "zh" else visual.description_en
        )
        ctk.CTkLabel(
            card,
            text=title,
            anchor="w",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=FONT_BODY, weight="bold"),
        ).grid(row=0, column=1, sticky="sw", padx=(0, 12), pady=(13, 2))
        ctk.CTkLabel(
            card,
            text=description,
            anchor="w",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=FONT_SMALL),
        ).grid(row=1, column=1, sticky="nw", padx=(0, 12), pady=(2, 13))
        card.grid_columnconfigure(1, weight=1)
