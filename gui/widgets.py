from __future__ import annotations

import customtkinter as ctk

from gui.theme import INPUT_HEIGHT, TYPO, CARD_RADIUS, BTN_HEIGHT, SIDEBAR_WIDTH, CONTENT_PADX, Theme


def fnt(size: int, weight: str = "normal") -> ctk.CTkFont:
    if weight != "normal":
        return ctk.CTkFont(size=size, weight=weight)
    return ctk.CTkFont(size=size)


font = fnt


class PageHeader(ctk.CTkFrame):
    """主内容区页眉：大标题 + 灰色副标题。"""

    def __init__(self, master, theme: Theme) -> None:
        super().__init__(master, fg_color="transparent")
        self.title = ctk.CTkLabel(self, text="", font=fnt(TYPO.page_title, "bold"), text_color=theme.text_title, anchor="w")
        self.title.pack(anchor="w")
        self.subtitle = ctk.CTkLabel(self, text="", font=fnt(TYPO.page_subtitle), text_color=theme.text_muted, anchor="w")
        self.subtitle.pack(anchor="w", pady=(6, 0))

    def set(self, title: str, subtitle: str = "") -> None:
        self.title.configure(text=title)
        self.subtitle.configure(text=subtitle)


class SectionTitle(ctk.CTkLabel):
    def __init__(self, master, theme: Theme, text: str) -> None:
        super().__init__(master, text=text, font=fnt(TYPO.section, "bold"), text_color=theme.text_title, anchor="w")


class SectionHeader(SectionTitle):
    pass


class FieldLabel(ctk.CTkLabel):
    def __init__(self, master, theme: Theme, text: str, *, required: bool = False) -> None:
        label = f"{text} *" if required else text
        super().__init__(master, text=label, font=fnt(TYPO.label, "bold"), text_color=theme.text_title, anchor="w")


class HintLabel(ctk.CTkLabel):
    def __init__(self, master, theme: Theme, text: str) -> None:
        super().__init__(master, text=text, font=fnt(TYPO.hint), text_color=theme.text_hint, anchor="w", justify="left")


class FormField(ctk.CTkFrame):
    def __init__(
        self,
        master,
        theme: Theme,
        label: str,
        *,
        required: bool = False,
        hint: str = "",
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        FieldLabel(self, theme, label, required=required).grid(row=0, column=0, sticky="w")
        self.entry = ctk.CTkEntry(
            self,
            height=INPUT_HEIGHT,
            font=fnt(TYPO.body),
            fg_color=theme.bg_input,
            border_color=theme.border,
            text_color=theme.text,
            corner_radius=8,
        )
        self.entry.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        if hint:
            HintLabel(self, theme, hint).grid(row=2, column=0, sticky="w", pady=(6, 0))

    def get(self) -> str:
        return self.entry.get()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, value)

    def configure_entry(self, **kwargs) -> None:
        self.entry.configure(**kwargs)


class InfoRow(ctk.CTkFrame):
    def __init__(self, master, theme: Theme, label: str) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=label, font=fnt(TYPO.body), text_color=theme.text_muted, width=100, anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        self.value = ctk.CTkLabel(self, text="-", font=fnt(TYPO.body), text_color=theme.text, anchor="w")
        self.value.grid(row=0, column=1, sticky="w")

    def set(self, text: str, *, link: bool = False, theme: Theme | None = None) -> None:
        kw: dict = {"text": text}
        if link and theme:
            kw["text_color"] = theme.accent_link
            kw["cursor"] = "hand2"
        self.value.configure(**kw)


class FeatureCard(ctk.CTkFrame):
    def __init__(self, master, theme: Theme, icon: str, title: str, line1: str, line2: str) -> None:
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text=icon, font=fnt(20)).pack(anchor="w")
        ctk.CTkLabel(self, text=title, font=fnt(TYPO.feature_title, "bold"), text_color=theme.text_title, anchor="w").pack(
            anchor="w", pady=(6, 2)
        )
        ctk.CTkLabel(self, text=line1, font=fnt(TYPO.feature_desc), text_color=theme.text_muted, anchor="w").pack(anchor="w")
        ctk.CTkLabel(self, text=line2, font=fnt(TYPO.feature_desc), text_color=theme.text_muted, anchor="w").pack(anchor="w")


class ChecklistRow(ctk.CTkFrame):
    def __init__(self, master, theme: Theme, label: str) -> None:
        super().__init__(master, fg_color="transparent")
        self.icon = ctk.CTkLabel(self, text="○", font=fnt(TYPO.body), text_color=theme.text_hint, width=24)
        self.icon.pack(side="left")
        ctk.CTkLabel(self, text=label, font=fnt(TYPO.body), text_color=theme.text, anchor="w").pack(side="left", fill="x", expand=True)
        self.status = ctk.CTkLabel(self, text="", font=fnt(TYPO.body))
        self.status.pack(side="right")

    def set_pending(self) -> None:
        self.icon.configure(text="○", text_color="#9CA3AF")
        self.status.configure(text="")

    def set_ok(self, text: str = "OK") -> None:
        self.icon.configure(text="✓", text_color="#16A34A")
        self.status.configure(text=text, text_color="#16A34A")

    def set_fail(self, text: str = "Fail") -> None:
        self.icon.configure(text="✗", text_color="#DC2626")
        self.status.configure(text=text, text_color="#DC2626")
