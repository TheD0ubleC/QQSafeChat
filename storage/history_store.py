
from __future__ import annotations
import json
import os
import re
import time
from typing import List, Dict, Any, Optional

from core.models import ExtractedMessage


_TS_PREFIX_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(.*)$")
_READABLE_LINE_RE = re.compile(r"^\[(?P<ts>[\d\-: ]+)\]\s*\[(?P<label>.+?)\]\s*(?P<text>.*)$")


class HistoryStore:
    def __init__(self, path: str, max_messages: int, selected_name: str | None = None):
        self.base_dir, self.default_name = self._resolve_base(path)
        self.max_messages = max_messages
        self.current_name: str = self._sanitize_name(selected_name) or self.default_name
        self.items: List[Dict[str, Any]] = []  
        self._load(self.current_name)

    
    def _resolve_base(self, path: str) -> tuple[str, str]:
        if os.path.isdir(path):
            base_dir = path
            default_name = "default"
        else:
            base_dir = os.path.dirname(path) or "."
            default_name = os.path.splitext(os.path.basename(path))[0] or "default"

        os.makedirs(base_dir, exist_ok=True)
        return base_dir, default_name

    def _sanitize_name(self, name: str | None) -> str:
        if name is None:
            return ""
        name = name.strip()
        name = name.replace(os.path.sep, "_")
        name = name.replace("..", "")
        name = re.sub(r"[\\/:*?\"<>|]", "_", name)
        return name

    def _history_path(self, name: str | None = None) -> str:
        name = self._sanitize_name(name) or self.default_name
        return os.path.join(self.base_dir, f"{name}.jsonl")

    
    def _fmt_ts(self, ts: float | int | None) -> str:
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))
        except Exception:
            return ""

    def _sender_label(self, sender: str) -> str:
        return "自己" if sender == "self" else ("对方" if sender == "other" else "未知")

    def _label_to_sender(self, label: str) -> str:
        label = (label or "").strip()
        if label in ("自己", "self"):
            return "self"
        if label in ("对方", "other"):
            return "other"
        return "unknown"

    
    def _ensure_ts_prefix(self, ts_val: float | int, text: str) -> str:
        text = str(text or "")
        m = _TS_PREFIX_RE.match(text.strip())
        if m:
            return text  
        ts_str = self._fmt_ts(ts_val) or self._fmt_ts(time.time())
        return f"[{ts_str}] {text}"

    def _strip_ts_prefix(self, text: str) -> str:
        text = str(text or "").strip()
        m = _TS_PREFIX_RE.match(text)
        if not m:
            return text
        return (m.group(2) or "").strip()

    def _split_ts_prefix(self, text: str) -> tuple[Optional[str], str]:
        text = str(text or "").strip()
        m = _TS_PREFIX_RE.match(text)
        if not m:
            return None, text
        return (m.group(1) or "").strip(), (m.group(2) or "")

    
    def _parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        line = (line or "").strip()
        if not line:
            return None

        
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    obj.setdefault("ts", time.time())
                    obj.setdefault("sender", "unknown")
                    obj.setdefault("text", "")
                    
                    try:
                        ts_val = float(obj.get("ts") or time.time())
                    except Exception:
                        ts_val = time.time()
                    obj["text"] = self._ensure_ts_prefix(ts_val, str(obj.get("text") or ""))
                    return obj
            except Exception:
                pass

        
        m = _READABLE_LINE_RE.match(line)
        if m:
            ts_str = (m.group("ts") or "").strip()
            label = (m.group("label") or "").strip()
            text = m.group("text") or ""

            ts_val = time.time()
            try:
                st = time.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                ts_val = time.mktime(st)
            except Exception:
                ts_val = time.time()

            
            return {
                "ts": ts_val,
                "sender": self._label_to_sender(label),
                "text": self._ensure_ts_prefix(ts_val, text),
            }

        return None

    
    def _load(self, name: str):
        self.items = []
        path = self._history_path(name)
        if not os.path.exists(path):
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    obj = self._parse_line(line)
                    if not obj:
                        continue
                    obj.setdefault("ts", time.time())
                    obj.setdefault("sender", "unknown")
                    obj.setdefault("text", "")
                    self.items.append(obj)
        except Exception:
            self.items = []

        if len(self.items) > self.max_messages:
            self.items = self.items[-self.max_messages :]

    def _save_items(self, path: str):
        try:
            with open(path, "w", encoding="utf-8") as f:
                for it in self.items[-self.max_messages:]:
                    
                    try:
                        ts_val = float(it.get("ts") or time.time())
                    except Exception:
                        ts_val = time.time()
                    it2 = {
                        "ts": ts_val,
                        "sender": str(it.get("sender") or "unknown"),
                        "text": self._ensure_ts_prefix(ts_val, str(it.get("text") or "")),
                    }
                    f.write(json.dumps(it2, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def save(self):
        path = self._history_path(self.current_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._save_items(path)

    def clear(self):
        self.items = []
        path = self._history_path(self.current_name)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    
    def list_histories(self) -> list[str]:
        names: list[str] = []
        try:
            for fname in os.listdir(self.base_dir):
                if fname.endswith(".jsonl"):
                    names.append(os.path.splitext(fname)[0])
        except Exception:
            pass
        if self.default_name not in names:
            names.append(self.default_name)
        names = [self._sanitize_name(n) for n in names if self._sanitize_name(n)]
        names = sorted(set(names), key=lambda s: s.lower())
        return names

    
    def switch(self, name: str) -> str:
        target = self._sanitize_name(name) or self.default_name
        self.current_name = target
        self._load(target)
        return target

    def ensure_history(self, name: str) -> str:
        target = self._sanitize_name(name) or self.default_name
        path = self._history_path(target)
        if not os.path.exists(path):
            os.makedirs(self.base_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
        return self.switch(target)

    def create(self, name: str) -> Optional[str]:
        target = self._sanitize_name(name)
        if not target:
            return None
        path = self._history_path(target)
        if os.path.exists(path):
            return None
        try:
            os.makedirs(self.base_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            return target
        except Exception:
            return None

    def rename(self, old: str, new: str) -> bool:
        old = self._sanitize_name(old) or self.default_name
        new = self._sanitize_name(new)
        if not new:
            return False
        src = self._history_path(old)
        dst = self._history_path(new)
        if not os.path.exists(src) or (os.path.exists(dst) and old != new):
            return False
        try:
            os.rename(src, dst)
            if self.current_name == old:
                self.current_name = new
                self._load(new)
            return True
        except Exception:
            return False

    def delete(self, name: str) -> bool:
        name = self._sanitize_name(name)
        if not name:
            return False
        path = self._history_path(name)
        if not os.path.exists(path):
            return False
        try:
            os.remove(path)
            if self.current_name == name:
                fallback = self.default_name
                if fallback == name:
                    available = [n for n in self.list_histories() if n != name]
                    if available:
                        fallback = available[0]
                self.switch(fallback)
            return True
        except Exception:
            return False

    
    def append_messages(self, msgs: List[ExtractedMessage]):
        now = time.time()
        for m in msgs:
            ts = getattr(m, "ts", None) or now
            sender = getattr(m, "sender", None) or "unknown"
            raw_text = str(getattr(m, "text", "") or "")

            
            text_with_ts = self._ensure_ts_prefix(ts, raw_text)

            
            if self.items:
                last = self.items[-1]
                if str(last.get("sender")) == str(sender):
                    last_body = self._strip_ts_prefix(str(last.get("text") or ""))
                    cur_body = self._strip_ts_prefix(text_with_ts)
                    if last_body == cur_body and cur_body != "":
                        continue

            self.items.append({
                "ts": ts,
                "sender": sender,
                "text": text_with_ts,
            })

        if len(self.items) > self.max_messages:
            self.items = self.items[-self.max_messages :]

        self.save()

    def format_for_prompt(self, last_n: Optional[int] = None) -> str:
        data = self.items if last_n is None else self.items[-last_n:]

        
        last_invalid_idx = -1
        for i, it in enumerate(data):
            ts_str = self._fmt_ts(it.get("ts"))
            if not ts_str:
                last_invalid_idx = i

        if last_invalid_idx >= 0:
            data = data[last_invalid_idx + 1 :]

        lines: List[str] = []
        for it in data:
            sender = str(it.get("sender") or "unknown")
            who = "自己" if sender == "self" else ("对方" if sender == "other" else "未知")

            text = str(it.get("text") or "")
            ts_in_text, body = self._split_ts_prefix(text)

            if ts_in_text:
                
                body_lines = (body or "").splitlines() or [""]
                for ln in body_lines:
                    lines.append(f"[{ts_in_text}] [{who}] {ln}")
            else:
                
                ts_str = self._fmt_ts(it.get("ts"))
                body_lines = text.splitlines() or [""]
                for ln in body_lines:
                    lines.append(f"[{ts_str}] [{who}] {ln}")

        return "\n".join(lines)

    
    def export_raw_text(self, name: str | None = None) -> str:
        target = name or self.current_name
        path = self._history_path(target)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                return ""
        return "\n".join(json.dumps(it, ensure_ascii=False) for it in self.items)

    def import_raw_text(self, text: str, name: str | None = None) -> bool:
        target = name or self.current_name
        lines: List[Dict[str, Any]] = []
        for ln in (text or "").splitlines():
            obj = self._parse_line(ln)
            if not obj:
                continue
            obj.setdefault("ts", time.time())
            obj.setdefault("sender", "unknown")
            obj.setdefault("text", "")
            
            try:
                ts_val = float(obj.get("ts") or time.time())
            except Exception:
                ts_val = time.time()
            obj["text"] = self._ensure_ts_prefix(ts_val, str(obj.get("text") or ""))
            lines.append(obj)

        self.items = lines[-self.max_messages :]
        self.current_name = self._sanitize_name(target) or self.default_name
        self.save()
        return True
