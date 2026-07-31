from __future__ import annotations

import customtkinter as ctk

from gui.theme import COLORS

_KIND_META = {
    "success": ("✓", COLORS["success"]),
    "error": ("✗", COLORS["danger"]),
    "info": ("ℹ", COLORS["primary"]),
    "warning": ("!", COLORS["warning"]),
}


class ResultDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent: ctk.CTk,
        *,
        title: str,
        message: str,
        kind: str = "info",
        copy_label: str = "Copy",
        ok_label: str = "OK",
        subtitle: str = "",
    ) -> None:
        super().__init__(parent)
        self._message = message
        self.title(title)
        self.configure(fg_color=COLORS["bg"])
        self.transient(parent)
        self.resizable(True, True)
        self.geometry("680x520")
        self.minsize(560, 380)

        icon, accent = _KIND_META.get(kind, _KIND_META["info"])

        shell = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        shell.pack(fill="both", expand=True, padx=20, pady=20)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(
            shell, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"],
        )
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.grid_columnconfigure(1, weight=1)

        badge = ctk.CTkLabel(
            header, text=icon, width=42, height=42,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#FFFFFF", fg_color=accent, corner_radius=21,
        )
        badge.grid(row=0, column=0, rowspan=2, padx=(20, 14), pady=18, sticky="w")

        ctk.CTkLabel(
            header, text=title, font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"], anchor="w",
        ).grid(row=0, column=1, padx=(0, 20), pady=(18, 4), sticky="ew")

        if not subtitle:
            subtitle = {
                "success": "Operation completed",
                "error": "Operation failed",
                "info": "Details",
                "warning": "Please review",
            }.get(kind, "Details")
        ctk.CTkLabel(
            header, text=subtitle, font=ctk.CTkFont(size=13),
            text_color=COLORS["muted"], anchor="w",
        ).grid(row=1, column=1, padx=(0, 20), pady=(0, 18), sticky="ew")

        body = ctk.CTkFrame(
            shell, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"],
        )
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        mono = "Consolas" if parent.tk.call("tk", "windowingsystem") == "win32" else "monospace"
        self.textbox = ctk.CTkTextbox(
            body, font=(mono, 13), fg_color=COLORS["surface_alt"],
            border_width=1, border_color=COLORS["border"], corner_radius=10,
            wrap="word",
        )
        self.textbox.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        self.textbox.insert("1.0", message)
        self.textbox.configure(state="disabled")

        footer = ctk.CTkFrame(shell, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="e", pady=(12, 0))

        ctk.CTkButton(
            footer, text=copy_label, width=96, height=36,
            fg_color="transparent", border_width=1, border_color=COLORS["border"],
            text_color=COLORS["text"], hover_color=COLORS["surface_alt"],
            command=self._copy,
        ).pack(side="left", padx=(0, 8))

        ok_btn = ctk.CTkButton(
            footer, text=ok_label, width=96, height=36,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            command=self.destroy,
        )
        ok_btn.pack(side="left")
        ok_btn.focus_set()

        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()
        self.after(10, lambda: self._center_on(parent))

    def _copy(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self._message)
        self.update()

    def _center_on(self, parent: ctk.CTk) -> None:
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + max(0, (pw - width) // 2)
        y = py + max(0, (ph - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")


def show_result_dialog(
    parent: ctk.CTk,
    *,
    title: str,
    message: str,
    kind: str = "info",
    copy_label: str = "Copy",
    ok_label: str = "OK",
    subtitle: str = "",
) -> None:
    ResultDialog(
        parent, title=title, message=message, kind=kind,
        copy_label=copy_label, ok_label=ok_label, subtitle=subtitle,
    )
