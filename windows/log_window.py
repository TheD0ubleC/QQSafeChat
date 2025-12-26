from __future__ import annotations

import tkinter as tk

from windows.ui_theme import (
    DARK_TEXT_BG,
    DARK_TEXT_FG,
    DARK_TEXT_INSERT,
    FONT_MONO,
    FONT_TITLE,
    THEME_NAME,
    _BOOTSTRAP,
    apply_window_icon,
    ttk,
)


class LogWindow(tk.Toplevel):

    def __init__(self, master: tk.Tk, initial_lines: list[str], on_clear, on_close):
        super().__init__(master)
        apply_window_icon(self)
        self.title("日志（Status Log）")
        self.geometry("860x520")
        self.minsize(680, 360)

        self._on_clear = on_clear
        self._on_close = on_close

        self.protocol("WM_DELETE_WINDOW", self._handle_close)

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(
            top, text="Status 日志（所有 ui_status 都会记录）", font=FONT_TITLE
        ).pack(side="left")

        btns = ttk.Frame(top)
        btns.pack(side="right")

        ttk.Button(btns, text="清空", command=self._clear).pack(side="right")
        ttk.Button(btns, text="复制全部", command=self._copy_all).pack(
            side="right", padx=(0, 8)
        )

        body = ttk.Frame(self, padding=(10, 0, 10, 10))
        body.pack(fill="both", expand=True)

        if _BOOTSTRAP and THEME_NAME in ("darkly", "superhero", "cyborg"):
            self.text = tk.Text(
                body,
                wrap="none",
                font=FONT_MONO,
                bg=DARK_TEXT_BG,
                fg=DARK_TEXT_FG,
                insertbackground=DARK_TEXT_INSERT,
                relief="flat",
                highlightthickness=1,
                highlightbackground="#2a2a2a",
            )
        else:
            self.text = tk.Text(body, wrap="none", font=FONT_MONO)

        self.text.pack(side="left", fill="both", expand=True)

        yscroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        yscroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=yscroll.set)

        if initial_lines:
            self.text.insert(tk.END, "\n".join(initial_lines) + "\n")
            self.text.see(tk.END)

    def append_line(self, line: str):
        if not line:
            return
        try:
            self.text.insert(tk.END, line + "\n")
            self.text.see(tk.END)
        except Exception:
            pass

    def _clear(self):
        try:
            self.text.delete("1.0", tk.END)
        except Exception:
            pass
        try:
            self._on_clear()
        except Exception:
            pass

    def _copy_all(self):
        try:
            content = self.text.get("1.0", tk.END)
            self.clipboard_clear()
            self.clipboard_append(content)
        except Exception:
            pass

    def _handle_close(self):
        try:
            self._on_close()
        finally:
            try:
                self.destroy()
            except Exception:
                pass
