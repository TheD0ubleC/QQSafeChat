from __future__ import annotations

import ctypes
from ctypes import wintypes
import win32api
import win32gui
import win32con
import uiautomation as auto
from typing import Optional
from core.models import BoundControl

gdiplus = ctypes.WinDLL("gdiplus")
gdi32 = ctypes.WinDLL("gdi32")
user32 = ctypes.WinDLL("user32")
Ok = 0
SmoothingModeAntiAlias = 4
TextRenderingHintAntiAliasGridFit = 3
UnitPixel = 2
FontStyleRegular = 0

StringAlignmentNear = 0
StringAlignmentCenter = 1

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01

DIB_RGB_COLORS = 0


class GdiplusStartupInput(ctypes.Structure):
    _fields_ = [
        ("GdiplusVersion", wintypes.UINT),
        ("DebugEventCallback", wintypes.LPVOID),
        ("SuppressBackgroundThread", wintypes.BOOL),
        ("SuppressExternalCodecs", wintypes.BOOL),
    ]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", wintypes.BYTE),
        ("BlendFlags", wintypes.BYTE),
        ("SourceConstantAlpha", wintypes.BYTE),
        ("AlphaFormat", wintypes.BYTE),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class RECTF(ctypes.Structure):
    _fields_ = [
        ("X", ctypes.c_float),
        ("Y", ctypes.c_float),
        ("Width", ctypes.c_float),
        ("Height", ctypes.c_float),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


BI_RGB = 0


def _check(status: int, where: str):
    if status != Ok:
        raise RuntimeError(f"GDI+ call failed ({where}): status={status}")


# Function prototypes (only what we use)
gdiplus.GdiplusStartup.argtypes = [
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(GdiplusStartupInput),
    wintypes.LPVOID,
]
gdiplus.GdiplusStartup.restype = ctypes.c_int
gdiplus.GdiplusShutdown.argtypes = [ctypes.c_void_p]
gdiplus.GdiplusShutdown.restype = None

gdiplus.GdipCreateFromHDC.argtypes = [wintypes.HDC, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreateFromHDC.restype = ctypes.c_int
gdiplus.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeleteGraphics.restype = ctypes.c_int

gdiplus.GdipSetSmoothingMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetSmoothingMode.restype = ctypes.c_int
gdiplus.GdipSetTextRenderingHint.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetTextRenderingHint.restype = ctypes.c_int
gdiplus.GdipGraphicsClear.argtypes = [ctypes.c_void_p, wintypes.DWORD]
gdiplus.GdipGraphicsClear.restype = ctypes.c_int

gdiplus.GdipCreatePen1.argtypes = [
    wintypes.DWORD,
    ctypes.c_float,
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_void_p),
]
gdiplus.GdipCreatePen1.restype = ctypes.c_int
gdiplus.GdipDeletePen.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeletePen.restype = ctypes.c_int
gdiplus.GdipDrawRectangle.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_float,
    ctypes.c_float,
    ctypes.c_float,
    ctypes.c_float,
]
gdiplus.GdipDrawRectangle.restype = ctypes.c_int

gdiplus.GdipCreateSolidFill.argtypes = [wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreateSolidFill.restype = ctypes.c_int
gdiplus.GdipDeleteBrush.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeleteBrush.restype = ctypes.c_int

gdiplus.GdipCreatePath.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreatePath.restype = ctypes.c_int
gdiplus.GdipDeletePath.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeletePath.restype = ctypes.c_int

gdiplus.GdipCreateFontFamilyFromName.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPVOID,
    ctypes.POINTER(ctypes.c_void_p),
]
gdiplus.GdipCreateFontFamilyFromName.restype = ctypes.c_int
gdiplus.GdipDeleteFontFamily.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeleteFontFamily.restype = ctypes.c_int

gdiplus.GdipCreateStringFormat.argtypes = [
    ctypes.c_int,
    wintypes.LANGID,
    ctypes.POINTER(ctypes.c_void_p),
]
gdiplus.GdipCreateStringFormat.restype = ctypes.c_int
gdiplus.GdipDeleteStringFormat.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeleteStringFormat.restype = ctypes.c_int
gdiplus.GdipSetStringFormatAlign.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetStringFormatAlign.restype = ctypes.c_int
gdiplus.GdipSetStringFormatLineAlign.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetStringFormatLineAlign.restype = ctypes.c_int

gdiplus.GdipAddPathString.argtypes = [
    ctypes.c_void_p,  # path
    wintypes.LPCWSTR,  # string
    ctypes.c_int,  # length
    ctypes.c_void_p,  # fontFamily
    ctypes.c_int,  # style
    ctypes.c_float,  # emSize
    ctypes.POINTER(RECTF),  # layoutRect
    ctypes.c_void_p,  # stringFormat
]
gdiplus.GdipAddPathString.restype = ctypes.c_int

gdiplus.GdipFillPath.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
gdiplus.GdipFillPath.restype = ctypes.c_int
gdiplus.GdipDrawPath.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
gdiplus.GdipDrawPath.restype = ctypes.c_int


def _argb(a: int, r: int, g: int, b: int) -> int:
    return ((a & 0xFF) << 24) | ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)


class _GDIPlusRuntime:
    _token: ctypes.c_void_p | None = None

    @classmethod
    def ensure(cls):
        if cls._token is not None:
            return
        token = ctypes.c_void_p()
        startup = GdiplusStartupInput(1, None, False, False)
        status = gdiplus.GdiplusStartup(
            ctypes.byref(token), ctypes.byref(startup), None
        )
        _check(status, "GdiplusStartup")
        cls._token = token

    @classmethod
    def shutdown(cls):
        if cls._token is not None:
            gdiplus.GdiplusShutdown(cls._token)
            cls._token = None


class HighlightRect:

    _BORDER_RGB = (255, 255, 0)  # 这是最好的颜色 最好不要乱改
    _BORDER_WIDTH = 3.0
    _TEXT_STROKE = 0

    def __init__(self):
        _GDIPlusRuntime.ensure()

        self._label: str = ""
        self._last_rect_key: tuple[int, int, int, int] | None = None

        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self.wnd_proc
        wc.lpszClassName = "HighlightRect_UiaChatbot"
        wc.hInstance = win32api.GetModuleHandle(None)

        try:
            self.class_atom = win32gui.RegisterClass(wc)
        except win32gui.error:
            self.class_atom = win32gui.GetClassInfo(wc.hInstance, wc.lpszClassName)[0]

        self.hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_TOPMOST
            | win32con.WS_EX_TOOLWINDOW,
            self.class_atom,
            None,
            win32con.WS_POPUP,
            0,
            0,
            0,
            0,
            0,
            0,
            wc.hInstance,
            None,
        )
        win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)

    def wnd_proc(self, hwnd, msg, w, l):
        if msg == win32con.WM_NCHITTEST:
            return win32con.HTTRANSPARENT
        return win32gui.DefWindowProc(hwnd, msg, w, l)

    def _label_from_ctrl(self, ctrl: Optional[auto.Control]) -> str:
        if not ctrl:
            return ""
        try:
            return getattr(ctrl, "ControlTypeName", "") or ""
        except Exception:
            return ""

    def _auto_pick_label_by_rect_center(self, rect) -> str:
        try:
            cx = int((rect.left + rect.right) / 2)
            cy = int((rect.top + rect.bottom) / 2)
            ctrl = auto.ControlFromPoint(cx, cy)
            return self._label_from_ctrl(ctrl)
        except Exception:
            return ""

    def _update_layered(self, x: int, y: int, w: int, h: int, label: str):
        # screen dc
        hdc_screen = user32.GetDC(None)
        if not hdc_screen:
            return

        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        if not hdc_mem:
            user32.ReleaseDC(None, hdc_screen)
            return

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h  # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bmi.bmiHeader.biSizeImage = w * h * 4

        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(
            hdc_screen, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
        )
        if not hbmp:
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(None, hdc_screen)
            return

        old_bmp = gdi32.SelectObject(hdc_mem, hbmp)

        # ---- GDI+ draw into the DIB via HDC ----
        graphics = ctypes.c_void_p()
        status = gdiplus.GdipCreateFromHDC(hdc_mem, ctypes.byref(graphics))
        if status != Ok:
            gdi32.SelectObject(hdc_mem, old_bmp)
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(None, hdc_screen)
            return

        # smooth
        _check(
            gdiplus.GdipSetSmoothingMode(graphics, SmoothingModeAntiAlias),
            "SetSmoothingMode",
        )
        _check(
            gdiplus.GdipSetTextRenderingHint(
                graphics, TextRenderingHintAntiAliasGridFit
            ),
            "SetTextRenderingHint",
        )
        _check(
            gdiplus.GdipGraphicsClear(graphics, _argb(0, 0, 0, 0)), "GraphicsClear"
        )  # fully transparent

        # border (orange)
        pen_border = ctypes.c_void_p()
        br, bg, bb = self._BORDER_RGB
        _check(
            gdiplus.GdipCreatePen1(
                _argb(255, br, bg, bb),
                ctypes.c_float(self._BORDER_WIDTH),
                UnitPixel,
                ctypes.byref(pen_border),
            ),
            "CreatePen(border)",
        )

        inset = self._BORDER_WIDTH / 2.0
        _check(
            gdiplus.GdipDrawRectangle(
                graphics,
                pen_border,
                ctypes.c_float(inset),
                ctypes.c_float(inset),
                ctypes.c_float(max(1.0, w - self._BORDER_WIDTH)),
                ctypes.c_float(max(1.0, h - self._BORDER_WIDTH)),
            ),
            "DrawRectangle",
        )
        gdiplus.GdipDeletePen(pen_border)

        # text (white fill + black outline)
        label = (label or "").strip()
        if label and w >= 60 and h >= 30:
            base = min(w, h)
            font_px = int(base * 0.18)
            font_px = max(10, min(font_px, 40))

            family = ctypes.c_void_p()
            fmt = ctypes.c_void_p()
            path = ctypes.c_void_p()
            brush_white = ctypes.c_void_p()
            pen_black = ctypes.c_void_p()

            # font family
            _check(
                gdiplus.GdipCreateFontFamilyFromName(
                    "Segoe UI", None, ctypes.byref(family)
                ),
                "CreateFontFamily",
            )

            # string format (centered)
            _check(
                gdiplus.GdipCreateStringFormat(0, 0, ctypes.byref(fmt)),
                "CreateStringFormat",
            )
            _check(
                gdiplus.GdipSetStringFormatAlign(fmt, StringAlignmentCenter), "SetAlign"
            )
            _check(
                gdiplus.GdipSetStringFormatLineAlign(fmt, StringAlignmentCenter),
                "SetLineAlign",
            )

            # path
            _check(gdiplus.GdipCreatePath(0, ctypes.byref(path)), "CreatePath")

            # layout rect (padding a bit)
            pad = 6.0
            rectf = RECTF(
                pad, pad, float(max(1, w)) - pad * 2.0, float(max(1, h)) - pad * 2.0
            )

            _check(
                gdiplus.GdipAddPathString(
                    path,
                    label,
                    -1,
                    family,
                    FontStyleRegular,
                    ctypes.c_float(font_px),
                    ctypes.byref(rectf),
                    fmt,
                ),
                "AddPathString",
            )

            _check(
                gdiplus.GdipCreateSolidFill(
                    _argb(255, 255, 255, 0), ctypes.byref(brush_white)
                ),
                "CreateSolidFill(white)",
            )
            _check(gdiplus.GdipFillPath(graphics, brush_white, path), "FillPath(white)")

            # black outline on top
            _check(
                gdiplus.GdipCreatePen1(
                    _argb(0, 0, 0, 0),
                    ctypes.c_float(self._TEXT_STROKE),
                    UnitPixel,
                    ctypes.byref(pen_black),
                ),
                "CreatePen(black)",
            )
            _check(gdiplus.GdipDrawPath(graphics, pen_black, path), "DrawPath(black)")

            # cleanup text objects
            gdiplus.GdipDeletePen(pen_black)
            gdiplus.GdipDeleteBrush(brush_white)
            gdiplus.GdipDeletePath(path)
            gdiplus.GdipDeleteStringFormat(fmt)
            gdiplus.GdipDeleteFontFamily(family)

        gdiplus.GdipDeleteGraphics(graphics)

        # ---- push to layered window ----
        pt_dst = POINT(x, y)
        size = SIZE(w, h)
        pt_src = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)

        user32.UpdateLayeredWindow(
            wintypes.HWND(self.hwnd),
            wintypes.HDC(hdc_screen),
            ctypes.byref(pt_dst),
            ctypes.byref(size),
            wintypes.HDC(hdc_mem),
            ctypes.byref(pt_src),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )

        # cleanup GDI objects
        gdi32.SelectObject(hdc_mem, old_bmp)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_screen)

    def show_control(self, ctrl: auto.Control):
        try:
            rect = ctrl.BoundingRectangle
        except Exception:
            return
        self._label = self._label_from_ctrl(ctrl)
        self.show_rect(rect)

    def show_rect(self, rect):
        left = int(rect.left)
        top = int(rect.top)
        right = int(rect.right)
        bottom = int(rect.bottom)

        width = max(0, right - left)
        height = max(0, bottom - top)

        if width <= 1 or height <= 1:
            self.hide()
            return

        rect_key = (left, top, right, bottom)
        if rect_key != self._last_rect_key:
            self._last_rect_key = rect_key
            self._label = self._auto_pick_label_by_rect_center(rect)

        self._update_layered(left, top, width, height, self._label)
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOWNOACTIVATE)

    def hide(self):
        win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)


# =========================
# rest of your helpers (unchanged)
# =========================


def find_child_control_by_type(
    ctrl, expected_type: str, max_depth: int = 3
) -> Optional[auto.Control]:
    """递归查找指定类型的子控件"""
    if not ctrl:
        return None

    try:
        if ctrl.ControlTypeName == expected_type:
            return ctrl
    except Exception:
        pass

    if max_depth <= 0:
        return None

    try:
        children = ctrl.GetChildren()
        for child in children:
            found = find_child_control_by_type(child, expected_type, max_depth - 1)
            if found:
                return found
    except Exception:
        pass

    return None


def control_from_point_safe(x: int, y: int, tk_hwnd: int) -> Optional[auto.Control]:
    hwnd = win32gui.WindowFromPoint((x, y))

    if hwnd == tk_hwnd or win32gui.IsChild(tk_hwnd, hwnd):
        return None
    try:
        ctrl = auto.ControlFromPoint(x, y)
        return ctrl
    except Exception:
        return None


def build_bound_control(ctrl, expected_type: str) -> Optional[BoundControl]:
    try:
        r = ctrl.BoundingRectangle
        cx = int((r.left + r.right) / 2)
        cy = int((r.top + r.bottom) / 2)
        return BoundControl(
            expected_type=expected_type,
            center_x=cx,
            center_y=cy,
            name=getattr(ctrl, "Name", "") or "",
            framework=getattr(ctrl, "FrameworkId", "") or "",
            automation_id=getattr(ctrl, "AutomationId", "") or "",
            class_name=getattr(ctrl, "ClassName", "") or "",
        )
    except Exception:
        return None


def reacquire(bound: BoundControl, tk_hwnd: int):
    offsets = [
        (0, 0),
        (8, 0),
        (-8, 0),
        (0, 8),
        (0, -8),
        (15, 0),
        (-15, 0),
        (0, 15),
        (0, -15),
    ]
    for dx, dy in offsets:
        ctrl = control_from_point_safe(
            bound.center_x + dx, bound.center_y + dy, tk_hwnd
        )
        if not ctrl:
            continue
        try:
            if ctrl.ControlTypeName == bound.expected_type:
                return ctrl
        except Exception:
            continue
    return None
