from __future__ import annotations
import time
import win32api
import win32con
import win32gui
import uiautomation as auto


def bring_to_foreground(hwnd: int | None):
    if not hwnd:
        return
    try:
        hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)  # 顶层窗口
    except Exception:
        pass
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    except Exception:
        pass
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def click_center(rect):
    x = int((rect.left + rect.right) / 2)
    y = int((rect.top + rect.bottom) / 2)
    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)


def try_click_button(button_ctrl, hwnd: int | None = None) -> str:
    bring_to_foreground(hwnd)
    time.sleep(0.03)
    try:
        ip = button_ctrl.GetPattern(auto.PatternId.InvokePattern)
        if ip:
            ip.Invoke()
            return "invoke"
    except Exception:
        pass

    try:
        try:
            button_ctrl.SetFocus()
        except Exception:
            pass
        time.sleep(0.05)
        auto.SendKeys("{ENTER}", waitTime=0.01)
        return "enter"
    except Exception:
        pass

    try:
        rect = button_ctrl.BoundingRectangle
        click_center(rect)
        return "mouse"
    except Exception:
        return "failed"


def try_input_text(edit_ctrl, text: str, hwnd: int | None = None) -> str:
    bring_to_foreground(hwnd)
    time.sleep(0.03)
    try:
        vp = edit_ctrl.GetPattern(auto.PatternId.ValuePattern)
        if vp:
            try:
                vp.SetValue(text)
            except Exception:
                pass
    except Exception:
        pass

    try:
        try:
            edit_ctrl.SetFocus()
        except Exception:
            pass

        time.sleep(0.05)
        auto.SendKeys("{CTRL}a{DEL}", waitTime=0.01)
        time.sleep(0.02)
        auto.SendKeys(text, waitTime=0.01)
        return "sendkeys"
    except Exception:
        pass
    try:
        rect = edit_ctrl.BoundingRectangle
        click_center(rect)
        time.sleep(0.06)

        try:
            edit_ctrl.SetFocus()
        except Exception:
            pass

        time.sleep(0.05)
        auto.SendKeys("{CTRL}a{DEL}", waitTime=0.01)
        time.sleep(0.02)
        auto.SendKeys(text, waitTime=0.01)
        return "click+sendkeys"
    except Exception:
        return "failed"
