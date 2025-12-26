
from __future__ import annotations
import json
import tkinter as tk
from typing import Any

from windows.ui_theme import ttk
from windows.ui_theme import apply_window_icon

class DebugWindow(tk.Toplevel):

    def __init__(self, master):
        super().__init__(master)
        apply_window_icon(self)
        self.title("LLM Debug - Request + Response")
        self.geometry("980x720")
        self.resizable(True, True)

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")

        self._title_var = tk.StringVar(value="等待第一条 debug 数据…")
        ttk.Label(top, textvariable=self._title_var).pack(side="left")

        btns = ttk.Frame(top)
        btns.pack(side="right")

        ttk.Button(btns, text="复制 System", command=self.copy_system).pack(side="left", padx=4)
        ttk.Button(btns, text="复制 User", command=self.copy_user).pack(side="left", padx=4)
        ttk.Button(btns, text="复制 Payload", command=self.copy_payload).pack(side="left", padx=4)
        ttk.Button(btns, text="复制 Raw Output", command=self.copy_raw_output).pack(side="left", padx=4)
        ttk.Button(btns, text="复制 Raw Response", command=self.copy_raw_response).pack(side="left", padx=4)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)

        
        self._system_text = self._make_tab("Request / System (最终)")
        self._user_text = self._make_tab("Request / User (最终)")
        self._payload_text = self._make_tab("Request / Payload JSON")
        self._meta_text = self._make_tab("Request / Meta")

        
        self._raw_output_text = self._make_tab("Response / Raw Output")
        self._parts_text = self._make_tab("Response / Parts (split)")
        self._usage_text = self._make_tab("Response / Usage + Finish")
        self._raw_response_text = self._make_tab("Response / Raw Response (截断显示)")
        self._error_text = self._make_tab("Error")

        self._last: dict[str, str] = {
            "system": "",
            "user": "",
            "payload": "",
            "meta": "",
            "raw_output": "",
            "parts": "",
            "usage_finish": "",
            "raw_response": "",
            "error": "",
        }

    def _make_tab(self, title: str) -> tk.Text:
        frm = ttk.Frame(self.nb)
        self.nb.add(frm, text=title)

        yscroll = ttk.Scrollbar(frm, orient="vertical")
        yscroll.pack(side="right", fill="y")

        txt = tk.Text(frm, wrap="word", font=("Consolas", 10))
        txt.pack(side="left", fill="both", expand=True)
        txt.configure(yscrollcommand=yscroll.set)
        yscroll.configure(command=txt.yview)
        return txt

    def _safe_json(self, obj: Any, limit: int = 20000) -> str:
        try:
            s = json.dumps(obj, ensure_ascii=False, indent=2)
        except Exception:
            try:
                s = str(obj)
            except Exception:
                s = "<unprintable>"

        if limit and len(s) > limit:
            s = s[:limit] + "\n... <truncated> ..."
        return s

    def _format_parts(self, parts: Any) -> str:
        if not parts:
            return ""
        if isinstance(parts, (list, tuple)):
            out = []
            for i, p in enumerate(parts, 1):
                out.append(f"[{i}] {p}")
            return "\n\n".join(out)
        return str(parts)

    def update_debug(self, data: dict):
        
        if "system" in data:
            self._last["system"] = (data.get("system") or "").strip()

        if "user" in data:
            self._last["user"] = (data.get("user") or "").strip()

        if "payload" in data:
            self._last["payload"] = json.dumps(data.get("payload") or {}, ensure_ascii=False, indent=2)

        if "meta" in data:
            self._last["meta"] = json.dumps(data.get("meta") or {}, ensure_ascii=False, indent=2)

        
        if "raw_output" in data:
            self._last["raw_output"] = (data.get("raw_output") or "").strip()

        if "parts" in data:
            self._last["parts"] = self._format_parts(data.get("parts"))

        if ("usage" in data) or ("finish_reason" in data):
            usage = data.get("usage") or {}
            finish = (data.get("finish_reason") or "").strip()
            blocks = []
            if finish:
                blocks.append(f"finish_reason: {finish}")
            if usage:
                blocks.append("usage:\n" + self._safe_json(usage, limit=8000))
            self._last["usage_finish"] = "\n\n".join(blocks)

        if "raw_response" in data:
            self._last["raw_response"] = self._safe_json(data.get("raw_response"))

        if "error" in data:
            self._last["error"] = (data.get("error") or "").strip()

        
        self._set_text(self._system_text, self._last.get("system", ""))
        self._set_text(self._user_text, self._last.get("user", ""))
        self._set_text(self._payload_text, self._last.get("payload", ""))
        self._set_text(self._meta_text, self._last.get("meta", ""))
        self._set_text(self._raw_output_text, self._last.get("raw_output", ""))
        self._set_text(self._parts_text, self._last.get("parts", ""))
        self._set_text(self._usage_text, self._last.get("usage_finish", ""))
        self._set_text(self._raw_response_text, self._last.get("raw_response", ""))
        self._set_text(self._error_text, self._last.get("error", ""))

    def _set_text(self, widget: tk.Text, content: str):
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)

    def _copy(self, s: str):
        try:
            self.clipboard_clear()
            self.clipboard_append(s or "")
        except Exception:
            pass

    def copy_system(self):
        self._copy(self._last.get("system", ""))

    def copy_user(self):
        self._copy(self._last.get("user", ""))

    def copy_payload(self):
        self._copy(self._last.get("payload", ""))

    def copy_raw_output(self):
        self._copy(self._last.get("raw_output", ""))

    def copy_raw_response(self):
        self._copy(self._last.get("raw_response", ""))
