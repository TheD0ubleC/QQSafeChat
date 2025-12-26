from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox
import win32api
import win32con
import win32gui
import uiautomation as auto
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from uia.uia_picker import HighlightRect, control_from_point_safe


MAX_NODES = 10000  # 最大节点数 如果显示不全可以改这个
MAX_DEPTH = 16  # 最大深度 如果选择整个窗口 建议把深度调整到16以上 如果选择消息列表 可以把这个改成 10（理论 8 足够）


class UIAComponentBrowserBootstrap:

    def __init__(self):
        self.win = ttk.Window(themename="darkly")
        self.win.title("QQSafeChat Debug - UIA 遍历工具")
        self.win.geometry("1320x860")

        self.tk_hwnd = self.win.winfo_id()

        self.picking = False
        self.hover_ctrl = None
        self.highlight = HighlightRect()

        self._item_meta: dict[str, dict] = {}

        self._payload_all: dict[str, str] = {}
        self._payload_type: dict[str, str] = {}

        self._hits: list[str] = []
        self._hit_idx: int = 0

        self.status_var = tk.StringVar(value="就绪")
        self.detail_var = tk.StringVar(value="节点信息：")
        self.search_var = tk.StringVar(value="")
        self.search_mode_var = tk.StringVar(value="All")

        self.show_type_var = tk.BooleanVar(value=False)
        self.show_name_var = tk.BooleanVar(value=False)
        self.show_value_var = tk.BooleanVar(value=True)
        self.show_aid_var = tk.BooleanVar(value=False)
        self.show_class_var = tk.BooleanVar(value=False)

        self._build_ui()
        self._apply_tree_style()
        self._bind()

        self.update_display_columns()

        self.win.after(30, self.pick_loop)
        self.win.mainloop()

    def _build_ui(self):
        top = ttk.Frame(self.win, padding=10)
        top.pack(fill=X)

        self.btn_pick = ttk.Button(
            top,
            text="按住拖拽选择组件（松开锁定）",
            bootstyle=PRIMARY,
        )
        self.btn_pick.pack(side=LEFT)

        ttk.Label(top, textvariable=self.status_var).pack(side=LEFT, padx=12)

        info = ttk.Frame(self.win, padding=(10, 0, 10, 6))
        info.pack(fill=X)
        ttk.Label(info, textvariable=self.detail_var, bootstyle=INFO).pack(anchor=W)

        bar = ttk.Frame(self.win, padding=(10, 0, 10, 10))
        bar.pack(fill=X)

        ttk.Label(bar, text="搜索：").pack(side=LEFT)
        self.search_entry = ttk.Entry(bar, textvariable=self.search_var, width=46)
        self.search_entry.pack(side=LEFT, padx=6)

        self.mode_box = ttk.Combobox(
            bar,
            textvariable=self.search_mode_var,
            values=["All", "ControlType"],
            width=14,
            state="readonly",
        )
        self.mode_box.pack(side=LEFT, padx=(0, 10))

        ttk.Button(bar, text="查找", command=self.do_search, bootstyle=SUCCESS).pack(
            side=LEFT
        )
        ttk.Button(bar, text="上一个", command=self.prev_hit).pack(side=LEFT, padx=4)
        ttk.Button(bar, text="下一个", command=self.next_hit).pack(side=LEFT)

        cols_box = ttk.Frame(bar)
        cols_box.pack(side=RIGHT)

        ttk.Label(cols_box, text="显示列：").pack(side=LEFT, padx=(0, 6))
        ttk.Checkbutton(
            cols_box,
            text="Type列",
            variable=self.show_type_var,
            command=self.update_display_columns,
            bootstyle=SECONDARY,
        ).pack(side=LEFT, padx=2)
        ttk.Checkbutton(
            cols_box,
            text="Name",
            variable=self.show_name_var,
            command=self.update_display_columns,
            bootstyle=SECONDARY,
        ).pack(side=LEFT, padx=2)
        ttk.Checkbutton(
            cols_box,
            text="Value",
            variable=self.show_value_var,
            command=self.update_display_columns,
            bootstyle=SECONDARY,
        ).pack(side=LEFT, padx=2)
        ttk.Checkbutton(
            cols_box,
            text="AutomationId",
            variable=self.show_aid_var,
            command=self.update_display_columns,
            bootstyle=SECONDARY,
        ).pack(side=LEFT, padx=2)
        ttk.Checkbutton(
            cols_box,
            text="ClassName",
            variable=self.show_class_var,
            command=self.update_display_columns,
            bootstyle=SECONDARY,
        ).pack(side=LEFT, padx=2)

        outer = ttk.Labelframe(self.win, text="UIA Tree", padding=(10, 8))
        outer.pack(fill=BOTH, expand=YES, padx=10, pady=(0, 10))

        main = ttk.Frame(outer)
        main.pack(fill=BOTH, expand=YES)

        cols = ("type", "name", "value", "aid", "class")
        self.tree = ttk.Treeview(main, columns=cols, show="tree headings")

        self.tree.heading("#0", text="层级 / ControlType")
        self.tree.heading("type", text="ControlType")
        self.tree.heading("name", text="Name")
        self.tree.heading("value", text="Value")
        self.tree.heading("aid", text="AutomationId")
        self.tree.heading("class", text="ClassName")

        self.tree.column("#0", width=340, stretch=False)
        self.tree.column("type", width=150, stretch=False)
        self.tree.column("name", width=240)
        self.tree.column("value", width=320)
        self.tree.column("aid", width=280)
        self.tree.column("class", width=220)

        vs = ttk.Scrollbar(main, orient=VERTICAL, command=self.tree.yview)
        hs = ttk.Scrollbar(main, orient=HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.tree.tag_configure("odd")
        self.tree.tag_configure("even")

    def _apply_tree_style(self):

        style = ttk.Style()

        try:
            style.configure("Treeview", rowheight=26, borderwidth=1, relief="solid")
            style.configure(
                "Treeview.Heading", font=("Segoe UI", 10, "bold"), relief="raised"
            )
        except Exception:
            pass

        odd_bg = "#1f232a"
        even_bg = "#252b33"
        self.tree.tag_configure("odd", background=odd_bg)
        self.tree.tag_configure("even", background=even_bg)

    def _bind(self):
        self.btn_pick.bind("<ButtonPress-1>", self.start_pick)
        self.btn_pick.bind("<ButtonRelease-1>", self.stop_pick_and_traverse)
        self.search_entry.bind("<Return>", lambda _e: self.do_search())
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

    def update_display_columns(self):

        display = []
        if self.show_type_var.get():
            display.append("type")
        if self.show_name_var.get():
            display.append("name")
        if self.show_value_var.get():
            display.append("value")
        if self.show_aid_var.get():
            display.append("aid")
        if self.show_class_var.get():
            display.append("class")

        if not display:
            self.show_value_var.set(True)
            display = ["value"]

        self.tree.configure(displaycolumns=display)

    def start_pick(self, _event=None):
        self.picking = True
        self.hover_ctrl = None
        win32api.SetCursor(win32gui.LoadCursor(0, win32con.IDC_CROSS))
        self.status_var.set("正在拾取：移到目标组件上，松开锁定…")

    def stop_pick_and_traverse(self, _event=None):
        self.picking = False
        win32api.SetCursor(win32gui.LoadCursor(0, win32con.IDC_ARROW))
        self.highlight.hide()

        ctrl = self.hover_ctrl
        self.hover_ctrl = None

        if not ctrl:
            self.status_var.set("未选中组件")
            return

        try:
            ctype = getattr(ctrl, "ControlTypeName", "") or ""
            name = getattr(ctrl, "Name", "") or ""
            self.status_var.set(f"已锁定组件：{ctype} | Name={name}")
        except Exception:
            self.status_var.set("已锁定组件（信息读取失败）")

        self._clear_tree()
        threading.Thread(
            target=self._build_and_populate, args=(ctrl,), daemon=True
        ).start()

    def pick_loop(self):
        if self.picking:
            x, y = win32api.GetCursorPos()
            ctrl = control_from_point_safe(x, y, self.tk_hwnd)
            if ctrl:
                self.hover_ctrl = ctrl
                try:
                    self.highlight.show_rect(ctrl.BoundingRectangle)
                except Exception:
                    pass
            else:
                self.highlight.hide()

        self.win.after(30, self.pick_loop)

    def _clear_tree(self):
        self.tree.delete(*self.tree.get_children())
        self._item_meta.clear()
        self._payload_all.clear()
        self._payload_type.clear()
        self._hits.clear()
        self._hit_idx = 0
        self.detail_var.set("节点信息：")

    @staticmethod
    def _s(x) -> str:
        try:
            return "" if x is None else str(x)
        except Exception:
            return ""

    def _get_value(self, ctrl) -> str:
        try:
            vp = ctrl.GetValuePattern()
            return vp.Value or ""
        except Exception:
            return ""

    def _snapshot(self, ctrl, depth: int) -> dict:
        try:
            ctype = self._s(getattr(ctrl, "ControlTypeName", ""))
            name = self._s(getattr(ctrl, "Name", ""))
            aid = self._s(getattr(ctrl, "AutomationId", ""))
            cls = self._s(getattr(ctrl, "ClassName", ""))
        except Exception:
            ctype, name, aid, cls = "", "", "", ""

        value = self._get_value(ctrl)

        try:
            hwnd = int(getattr(ctrl, "NativeWindowHandle", 0) or 0)
        except Exception:
            hwnd = 0
        try:
            pid = int(getattr(ctrl, "ProcessId", 0) or 0)
        except Exception:
            pid = 0
        try:
            tid = int(getattr(ctrl, "ThreadId", 0) or 0)
        except Exception:
            tid = 0

        return {
            "depth": depth,
            "type": ctype,
            "name": name,
            "value": value,
            "aid": aid,
            "class": cls,
            "hwnd": hwnd,
            "pid": pid,
            "tid": tid,
        }

    def _build_nodes(self, root_ctrl, max_depth=MAX_DEPTH, max_nodes=MAX_NODES):
        nodes = []

        def rec(ctrl, parent_idx: int, depth: int):
            if len(nodes) >= max_nodes or depth > max_depth:
                return
            snap = self._snapshot(ctrl, depth)
            my_idx = len(nodes)
            nodes.append({"parent": parent_idx, "snap": snap})
            try:
                children = ctrl.GetChildren()
            except Exception:
                return
            for ch in children:
                rec(ch, my_idx, depth + 1)

        rec(root_ctrl, -1, 0)
        return nodes

    def _build_and_populate(self, root_ctrl):
        try:
            with auto.UIAutomationInitializerInThread():
                nodes = self._build_nodes(root_ctrl)
        except Exception as e:
            self.win.after(0, lambda: messagebox.showerror("错误", str(e)))
            return

        self.win.after(0, lambda: self._populate_tree(nodes))

    def _populate_tree(self, nodes):
        idx_to_item: dict[int, str] = {}

        row_no = 0
        for idx, node in enumerate(nodes):
            parent_idx = node["parent"]
            snap = node["snap"]
            parent_item = "" if parent_idx < 0 else idx_to_item.get(parent_idx, "")

            text = f"[{snap['depth']}] {snap['type']}"

            value_display = snap["value"]
            if len(value_display) > 220:
                value_display = value_display[:220] + "…"

            values = (
                snap["type"],
                snap["name"],
                value_display,
                snap["aid"],
                snap["class"],
            )

            tag = "even" if (row_no % 2 == 0) else "odd"
            item = self.tree.insert(
                parent_item, "end", text=text, values=values, tags=(tag,)
            )
            idx_to_item[idx] = item
            row_no += 1

            self._item_meta[item] = snap

            all_payload = " ".join(
                [
                    text,
                    snap["type"],
                    snap["name"],
                    snap["value"],
                    snap["aid"],
                    snap["class"],
                ]
            ).lower()
            self._payload_all[item] = all_payload

            self._payload_type[item] = (snap["type"] or "").lower()

        self.status_var.set(
            f"遍历完成：{len(nodes)} 个节点（可搜索 ControlType / 全字段）"
        )

    def on_tree_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        meta = self._item_meta.get(item)
        if not meta:
            return

        hwnd = meta.get("hwnd", 0) or 0
        pid = meta.get("pid", 0) or 0
        tid = meta.get("tid", 0) or 0

        hwnd_str = f"0x{hwnd:X}" if hwnd else "N/A"
        self.detail_var.set(
            f"HWND={hwnd_str} | PID={pid or 'N/A'} | TID={tid or 'N/A'}"
            f" | Type={meta.get('type','')} | Name={meta.get('name','')}"
        )

    @staticmethod
    def _token_match(hay: str, key: str) -> bool:
        tokens = [t for t in key.strip().split() if t]
        return all(t in hay for t in tokens)

    def do_search(self):
        key = self.search_var.get().strip().lower()
        if not key:
            self.status_var.set("请输入搜索关键字")
            return

        mode = (self.search_mode_var.get() or "ControlType").strip()
        payload_map = self._payload_type if mode == "ControlType" else self._payload_all

        self._hits.clear()
        self._hit_idx = 0

        for item, payload in payload_map.items():
            if self._token_match(payload, key):
                self._hits.append(item)

        if not self._hits:
            self.status_var.set(f"未找到匹配项（模式：{mode}）")
            return

        self.status_var.set(f"找到 {len(self._hits)} 个匹配项（模式：{mode}）")
        self._focus_hit(0)

    def _focus_hit(self, idx: int):
        item = self._hits[idx]

        # 展开
        p = self.tree.parent(item)
        while p:
            self.tree.item(p, open=True)
            p = self.tree.parent(p)

        self.tree.selection_set(item)
        self.tree.see(item)

    def next_hit(self):
        if not self._hits:
            return
        self._hit_idx = (self._hit_idx + 1) % len(self._hits)
        self._focus_hit(self._hit_idx)

    def prev_hit(self):
        if not self._hits:
            return
        self._hit_idx = (self._hit_idx - 1) % len(self._hits)
        self._focus_hit(self._hit_idx)


if __name__ == "__main__":
    auto.uiautomation.SetGlobalSearchTimeout(1)
    UIAComponentBrowserBootstrap()
