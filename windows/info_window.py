from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from storage.config import AppConfig
from windows.ui_theme import (
    DARK_CANVAS_BG,
    DARK_CANVAS_FG,
    FONT_UI,
    LIGHT_CANVAS_BG,
    LIGHT_CANVAS_FG,
    THEME_NAME,
    _BOOTSTRAP,
    apply_window_icon,
    ttk,
)
from __version__ import __version__

class InfoWindow(tk.Toplevel):
    def __init__(self, master, cfg: AppConfig):
        super().__init__(master)
        apply_window_icon(self)
        self.cfg = cfg
        self.title("项目信息")
        self.geometry("480x320")

        if _BOOTSTRAP and THEME_NAME in ("darkly", "superhero", "cyborg"):
            canvas_bg = DARK_CANVAS_BG
            canvas_fg = DARK_CANVAS_FG
            border = "#333333"
        else:
            canvas_bg = LIGHT_CANVAS_BG
            canvas_fg = LIGHT_CANVAS_FG
            border = "#cccccc"

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        top = ttk.Frame(root)
        top.pack(fill="x")

        self.logo_holder = ttk.Frame(top, width=120, height=120)
        self.logo_holder.pack_propagate(False)
        self.logo_holder.grid_propagate(False)
        self.logo_holder.grid(row=0, column=0, sticky="nw", padx=0, pady=0)

        self.logo_canvas = tk.Canvas(
            self.logo_holder, bg=canvas_bg, highlightthickness=0
        )
        self.logo_canvas.pack(fill="both", expand=True, padx=4, pady=4)

        self.logo_path = Path(__file__).parent.parent / "docs" / "assets" / "Logo.png"
        self.logo_img = None  # hold reference to PhotoImage/ImageTk
        self._logo_orig = None
        self._has_pillow = False

        if self.logo_path.exists():
            try:
                from PIL import Image, ImageTk  # type: ignore

                self._logo_orig = Image.open(self.logo_path)
                self._has_pillow = True
            except Exception:
                try:
                    self.logo_img = tk.PhotoImage(file=str(self.logo_path))
                except Exception:
                    self._logo_orig = None

        def _draw(event=None):
            self.logo_canvas.delete("all")
            w = max(self.logo_canvas.winfo_width(), 16)
            h = max(self.logo_canvas.winfo_height(), 16)
            pad = 6

            if self._logo_orig and self._has_pillow:
                try:
                    img = self._logo_orig.copy().resize(
                        (max(1, w - pad * 2), max(1, h - pad * 2)), Image.LANCZOS
                    )
                    self.logo_img = ImageTk.PhotoImage(img)  # type: ignore
                    self.logo_canvas.create_image(w / 2, h / 2, image=self.logo_img)
                    return
                except Exception:
                    pass

            if self.logo_img:
                try:
                    self.logo_canvas.create_image(w / 2, h / 2, image=self.logo_img)
                    return
                except Exception:
                    pass

            self.logo_canvas.create_rectangle(0, 0, w, h, fill="#4a90e2", outline="")
            self.logo_canvas.create_text(
                w / 2,
                h / 2,
                text="LOGO",
                fill="white",
                font=("Segoe UI", max(10, int(min(w, h) / 6)), "bold"),
            )

        self.logo_canvas.bind("<Configure>", _draw)
        _draw()
        right = ttk.Frame(top)
        right.grid(row=0, column=1, sticky="nw", padx=12)
        top.grid_columnconfigure(1, weight=1)

        self.info1 = tk.StringVar(value="QQSafeChat")
        self.info2 = tk.StringVar(value=f"版本 Release-v{__version__}")
        self.info3 = tk.StringVar(value="★ Github Link")

        ttk.Label(right, textvariable=self.info1, font=("Segoe UI", 18, "bold")).pack(
            anchor="w"
        )
        ttk.Label(right, textvariable=self.info2).pack(anchor="w", pady=(4, 0))
        ttk.Label(
            right, textvariable=self.info3, foreground="#5893FF", cursor="hand2"
        ).pack(anchor="w", pady=(4, 0))

        self.info3_label = right.winfo_children()[-1]
        self.info3_label.bind("<Button-1>", self._open_github)

        ttk.Separator(root, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(root, text="项目简介").pack(anchor="w")
        self.desc_text = tk.Text(root, height=6, wrap="word", font=FONT_UI)
        self.desc_text.pack(fill="both", expand=True)
        self.desc_text.insert(
            "1.0",
            "QQSafeChat 是一个更安全的 QQ 聊天机器人工具，使用 UIA 获取聊天记录、输入框与发送按钮，避免被检测导致封号或冻结。\n\n支持调用本地 OpenAI-API 格式的模型，同时也支持多种在线大语言模型服务。提供了一些基础的人格设定。",
        )

    def _open_github(self, event=None):
        import webbrowser

        webbrowser.open_new("https://github.com/TheD0ubleC/QQSafeChat")

    def _entry_row(self, parent, label: str, var: tk.StringVar):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=14).pack(side="left")
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
