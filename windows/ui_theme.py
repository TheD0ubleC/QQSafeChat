
from __future__ import annotations
import tkinter as tk

_BOOTSTRAP = False
try:
    import ttkbootstrap as ttk 
    _BOOTSTRAP = True
except Exception: 
    from tkinter import ttk 


THEME_NAME = "darkly"  
FONT_UI = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 14, "bold")
FONT_MONO = ("Consolas", 10)


DARK_TEXT_BG = "#1e1e1e"
DARK_TEXT_FG = "#dcdcdc"
DARK_TEXT_INSERT = "#ffffff"


DARK_CANVAS_BG = "#202020"
DARK_CANVAS_FG = "#bbbbbb"
LIGHT_CANVAS_BG = "#f5f5f5"
LIGHT_CANVAS_FG = "#555555"

from pathlib import Path

_ASSETS_DIR = Path(__file__).resolve().parent / ".." / "docs" / "assets"
_APP_ICON = _ASSETS_DIR / "Logo.ico"
_APP_ICON_PNG = _ASSETS_DIR / "Logo.png"
_APP_ICON_IMAGE: tk.PhotoImage | None = None
def make_root_window() -> tk.Tk:
    if _BOOTSTRAP and hasattr(ttk, "Window"):
        try:
            root = ttk.Window(
                title="UIA AIChatBot",
                themename=THEME_NAME,
            )
            
            root.geometry("900x800")
            _set_window_icon(root)
            return root
        except Exception:
            pass

    root = tk.Tk()
    root.title("UIA AIChatBot")
    root.geometry("900x620")
    _set_window_icon(root)
    return root

def apply_window_icon(win: tk.Misc):
    global _APP_ICON_IMAGE
    try:
        if _APP_ICON_IMAGE is None:
            _APP_ICON_IMAGE = tk.PhotoImage(file=str(_APP_ICON_PNG))
        win.iconphoto(True, _APP_ICON_IMAGE)
    except Exception as e:
        print("apply_window_icon failed:", e)

def _set_window_icon(root: tk.Tk):
    try:
        if _APP_ICON.exists():
            root.withdraw() 
            root.iconbitmap(str(_APP_ICON))
            root.deiconify()
    except Exception as e:
        print("set icon failed:", e)


def apply_global_style(root: tk.Tk):
    try:
        style = ttk.Style()
    except Exception:
        return

    if not _BOOTSTRAP:
        try:
            style.theme_use("clam")
        except Exception:
            pass

    try:
        style.configure(".", font=FONT_UI)
        style.configure("TLabel", font=FONT_UI)
        style.configure("TButton", font=FONT_UI, padding=6)
        style.configure("TCheckbutton", font=FONT_UI, padding=4)
        style.configure("TRadiobutton", font=FONT_UI, padding=4)
        style.configure("TEntry", font=FONT_UI)
        style.configure("TCombobox", font=FONT_UI)
        style.configure("TLabelframe.Label", font=FONT_UI)
        style.configure("TNotebook.Tab", font=FONT_UI, padding=(10, 6))
    except Exception: 
        pass


__all__ = [
    "_BOOTSTRAP",
    "ttk",
    "THEME_NAME",
    "FONT_UI",
    "FONT_TITLE",
    "FONT_MONO",
    "DARK_TEXT_BG",
    "DARK_TEXT_FG",
    "DARK_TEXT_INSERT",
    "DARK_CANVAS_BG",
    "DARK_CANVAS_FG",
    "LIGHT_CANVAS_BG",
    "LIGHT_CANVAS_FG",
    "make_root_window",
    "apply_global_style",
]
