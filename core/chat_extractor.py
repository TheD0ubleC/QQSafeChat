
from __future__ import annotations
import re
import time
from typing import List, Optional
import uiautomation as auto
from core.models import ExtractedMessage

TIME_HHMM = re.compile(r"^\d{1,2}:\d{2}$")

DATE_TIME = re.compile(r"^\d{4}[/-]\d{1,2}[/-]\d{1,2}\s+\d{1,2}:\d{2}$")
DATE_ONLY = re.compile(r"^\d{4}[/-]\d{1,2}[/-]\d{1,2}$")

def _is_system_time_line(s: str) -> bool:
    s = s.strip()
    return bool(TIME_HHMM.match(s) or DATE_TIME.match(s) or DATE_ONLY.match(s))

def extract_messages(window_ctrl, list_rect, bubble_merge_gap_px: int = 26) -> List[ExtractedMessage]:
    list_center_x = (list_rect.left + list_rect.right) / 2

    raw: List[ExtractedMessage] = []

    def dfs(ctrl, current_sender_name: Optional[str] = None):
        try:
            ctype = ctrl.ControlTypeName
        except Exception:
            return

        
        next_sender_name = current_sender_name
        try:
            if ctype == "GroupControl":
                n = (ctrl.Name or "").strip()
                if n:
                    next_sender_name = n
        except Exception:
            pass

        if ctype == "TextControl":
            try:
                text = (ctrl.Name or "").strip()
                if text:
                    r = ctrl.BoundingRectangle
                    center_x = (r.left + r.right) / 2
                    sender = "other" if center_x < list_center_x else "self"
                    msg_type = "system_time" if _is_system_time_line(text) else "text"
                    raw.append(ExtractedMessage(
                        sender=sender,
                        text=text,
                        top=int(r.top),
                        left=int(r.left),
                        right=int(r.right),
                        debug_sender_name=next_sender_name,
                        msg_type=msg_type,
                        ts=time.time(),
                    ))
            except Exception:
                pass

        
        try:
            for child in ctrl.GetChildren():
                dfs(child, next_sender_name)
        except Exception:
            pass

    dfs(window_ctrl, None)

    
    raw.sort(key=lambda m: (m.top, m.left))

    
    raw2 = [m for m in raw if m.msg_type != "system_time"]

    
    merged: List[ExtractedMessage] = []
    for m in raw2:
        if not merged:
            merged.append(m)
            continue
        prev = merged[-1]
        if m.sender == prev.sender and abs(m.top - prev.top) <= bubble_merge_gap_px:
            
            prev.text = prev.text + "\n" + m.text
            prev.top = min(prev.top, m.top)
            prev.left = min(prev.left, m.left)
            prev.right = max(prev.right, m.right)
            if prev.ts is None:
                prev.ts = m.ts
        else:
            merged.append(m)

    return merged
