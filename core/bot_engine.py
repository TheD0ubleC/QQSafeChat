
from __future__ import annotations
from typing import List, Optional, Any, Tuple
import threading
import time
import random
import re
import hashlib
import os
import tempfile
import uuid
import struct
from collections import deque
import uiautomation as auto

from storage.config import AppConfig
from core.models import BoundControl, ExtractedMessage
from uia.uia_picker import reacquire
from core.chat_extractor import extract_messages
from storage.history_store import HistoryStore
from uia.uia_actions import try_input_text, try_click_button
from core.llm_client import BaseLLMClient
from storage.persona_store import PersonaStore
from features.sticker_selector import StickerSelectorClient


class BotEngine:

    def __init__(self, cfg: AppConfig, history: HistoryStore, llm: BaseLLMClient, tk_hwnd: int, ui_log, ui_status):
        self.cfg = cfg
        self.history = history
        self.llm = llm
        self.tk_hwnd = tk_hwnd
        self.ui_log = ui_log
        self.ui_status = ui_status

        self.running = False
        self.auto_reply = bool(cfg.auto_reply_enabled)

        self.bound_edit: Optional[BoundControl] = None
        self.bound_button: Optional[BoundControl] = None
        self.bound_window: Optional[BoundControl] = None

        self._busy_reply = False
        self._uia_lock = threading.RLock()
        self._history_lock = threading.RLock()

        
        self._baseline_taken = False

        
        self._last_other_sig: str = ""

        
        self._pending_incoming: List[ExtractedMessage] = []
        self._pending_reply_at: float = 0.0

        self.personas = PersonaStore(self.cfg.persona_dir)

        
        self._visible_max = 6

        
        
        self._echo_ttl_sec = 90.0
        self._recent_self_hash_ts: dict[str, float] = {}
        self._recent_self_text: deque[tuple[float, str]] = deque(maxlen=80)

    def is_ready(self) -> bool:
        return bool(self.bound_edit and self.bound_button and self.bound_window)

    def set_auto_reply(self, enabled: bool):
        self.auto_reply = enabled
        self.cfg.auto_reply_enabled = enabled

    def set_llm_client(self, llm: BaseLLMClient):
        self.llm = llm

    def start(self):
        if not self.is_ready():
            self.ui_status("❌ 需要先绑定：输入框(Edit) + 发送按钮(Button) + 消息列表(Window)")
            return

        self.running = True
        self._baseline_taken = False
        self._last_other_sig = ""
        self._pending_incoming = []
        self._pending_reply_at = 0.0

        
        self._recent_self_hash_ts.clear()
        self._recent_self_text.clear()

        self.ui_status("✅ AIChatBot 已启动（实时更新中）\n（如需对齐上次本地历史，建议聊天窗口右键->清空）")

    def stop(self):
        self.running = False
        self.ui_status("⏸️ 已停止")

    

    def _canon_text(self, s: str) -> str:
        s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
        
        s = re.sub(r"[ \t\u3000]+", " ", s)
        
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s.strip()

    def _sha1(self, s: str) -> str:
        return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()

    def _cleanup_echo(self, now: float):
        ttl = self._echo_ttl_sec
        
        dead = [k for k, ts in self._recent_self_hash_ts.items() if now - ts > ttl]
        for k in dead:
            self._recent_self_hash_ts.pop(k, None)
        
        while self._recent_self_text and (now - self._recent_self_text[0][0] > ttl):
            self._recent_self_text.popleft()

    def _register_self_outgoing(self, text: str):
        now = time.time()
        self._cleanup_echo(now)

        c = self._canon_text(text)
        if not c:
            return

        
        c_nospace = re.sub(r"\s+", "", c)

        fprints = set()
        fprints.add(self._sha1(c))
        fprints.add(self._sha1(c[:240]))
        fprints.add(self._sha1(c_nospace))
        fprints.add(self._sha1(c_nospace[:400]))

        for fp in fprints:
            self._recent_self_hash_ts[fp] = now
        self._recent_self_text.append((now, c))

    def _is_self_echo(self, maybe_other_text: str) -> bool:
        now = time.time()
        self._cleanup_echo(now)

        c = self._canon_text(maybe_other_text)
        if not c:
            return False

        c_nospace = re.sub(r"\s+", "", c)

        
        candidates = [
            self._sha1(c),
            self._sha1(c[:240]),
            self._sha1(c_nospace),
            self._sha1(c_nospace[:400]),
        ]
        for fp in candidates:
            ts = self._recent_self_hash_ts.get(fp)
            if ts and (now - ts <= self._echo_ttl_sec):
                return True

        
        
        if len(c) >= 40:
            for ts, sent in reversed(self._recent_self_text):
                if now - ts > self._echo_ttl_sec:
                    break
                
                if sent.startswith(c) or c.startswith(sent):
                    return True
                if len(c) >= 120 and c in sent:
                    return True

        return False

    

    def step(self):
        if not self.running or not self.is_ready():
            return

        with auto.UIAutomationInitializerInThread():
            with self._uia_lock:
                win = reacquire(self.bound_window, self.tk_hwnd)
                if not win:
                    self.ui_status("⚠️ 消息列表控件找不到了（窗口移动/刷新/焦点变化），请重新绑定")
                    return

                try:
                    list_rect = win.BoundingRectangle
                except Exception:
                    return

                msgs = extract_messages(win, list_rect)

        self.ui_log(self._format_visible(msgs))

        
        if not self._baseline_taken:
            last_other, last_idx = self._get_last_other(msgs)
            self._last_other_sig = self._make_last_other_sig(msgs, last_other, last_idx) if last_other else ""
            self._baseline_taken = True
            return

        
        last_other, last_idx = self._get_last_other(msgs)
        if last_other and last_other.text.strip():
            sig = self._make_last_other_sig(msgs, last_other, last_idx)
            if sig and sig != self._last_other_sig:
                
                self._last_other_sig = sig

                
                if self._is_self_echo(last_other.text):
                    self.ui_status("🧯 忽略疑似自己回显（UIA 误判成对方）")
                else:
                    with self._history_lock:
                        self.history.append_messages([last_other])

                    self.ui_status(f"🧠 已保存 1 条对方消息到本地历史（最多 {self.history.max_messages} 条）")

                    self._pending_incoming.append(last_other)
                    self._schedule_reply_from_now()

        
        if self.auto_reply and (not self._busy_reply) and self._pending_incoming and self._pending_reply_at > 0:
            if time.time() >= self._pending_reply_at:
                combined = "\n".join([m.text for m in self._pending_incoming])
                self._pending_incoming = []
                self._pending_reply_at = 0.0
                self._start_reply_thread(combined)

    

    def _get_last_other(self, msgs: List[ExtractedMessage]) -> tuple[Optional[ExtractedMessage], int]:
        for i in range(len(msgs) - 1, -1, -1):
            m = msgs[i]
            if m.sender == "other" and (m.text or "").strip():
                return m, i
        return None, -1

    def _norm(self, s: str) -> str:
        return (s or "").strip()

    def _make_last_other_sig(self, msgs: List[ExtractedMessage], last_other: ExtractedMessage, idx: int) -> str:
        lo = self._norm(last_other.text)

        prev_sender = ""
        prev_text = ""
        if 0 <= idx - 1 < len(msgs):
            pm = msgs[idx - 1]
            prev_sender = pm.sender or ""
            prev_text = self._norm(pm.text)

        return f"LO={lo}|P={prev_sender}:{prev_text}"

    

    def _schedule_reply_from_now(self):
        base = max(0.0, float(self.cfg.reply_stop_seconds))

        extra = 0.0
        mode = (self.cfg.reply_delay_mode or "fixed").strip().lower()
        if mode in ("fixed+random", "random", "rand"):
            a = float(self.cfg.reply_random_min)
            b = float(self.cfg.reply_random_max)
            if b < a:
                a, b = b, a
            extra = random.uniform(a, b)

        self._pending_reply_at = time.time() + base + extra
        self.ui_status(f"⏳ 检测到对方新消息：停发后将在 {base + extra:.2f}s 触发回复（mode={mode}）")

    

    def _format_ts_full(self, ts_val: float | int | None) -> str:
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts_val)))
        except Exception:
            return ""

    def _format_visible(self, msgs: List[ExtractedMessage]) -> str:
        lines: List[str] = []

        
        last_invalid_idx = -1
        for i, m in enumerate(msgs):
            if not self._format_ts_full(getattr(m, "ts", None)):
                last_invalid_idx = i

        effective_msgs = msgs[last_invalid_idx + 1 :]

        
        if self._visible_max and self._visible_max > 0:
            effective_msgs = effective_msgs[-self._visible_max :]

        for m in effective_msgs:
            who = "自己" if m.sender == "self" else ("对方" if m.sender == "other" else "未知")
            text_lines = (m.text or "").splitlines() or [""]
            prefixed = [f"[{who}] {ln}" for ln in text_lines]
            lines.append("\n".join(prefixed))

        return "💬 可见聊天（实时）\n\n" + ("\n\n".join(lines) if lines else "")

    

    def _load_persona_text(self) -> str:
        fname = (self.cfg.persona_file or "").strip()
        if not fname:
            return ""
        return self.personas.read(fname)

    def _attach_sticker_prompt(self, persona_text: str, split_delimiter: str) -> str:
        if not getattr(self.cfg, "sticker_selector_enabled", False):
            return persona_text

        prompt = getattr(self.cfg, "sticker_selector_prompt", "") or ""
        prompt = prompt.replace("{split_delimiter}", split_delimiter or "<<<NEXT>>>")
        prompt = prompt.strip()

        if not prompt:
            return persona_text

        parts = [persona_text.strip()] if persona_text.strip() else []
        parts.append("【StickerSelector 提示】\n" + prompt)
        return "\n\n".join(parts)

    

    def _start_reply_thread(self, incoming_combined: str):
        self._busy_reply = True
        self.ui_status("🤖 正在生成回复...")

        def worker():
            with auto.UIAutomationInitializerInThread():
                try:
                    with self._history_lock:
                        history_text = self.history.format_for_prompt(last_n=30)

                    persona_text = self._load_persona_text()
                    persona_text = self._attach_sticker_prompt(persona_text, self.cfg.split_delimiter)

                    reply = self.llm.generate_reply(
                        history_text,
                        incoming_combined,
                        persona_text=persona_text,
                        split_delimiter=self.cfg.split_delimiter,
                    ).strip()

                    if not reply:
                        self.ui_status("⚠️ AI 没生成内容")
                        return

                    parts = self._split_reply(reply)
                    send_parts, history_parts = self._prepare_sticker_parts(parts)
                    ok = self._send_parts(send_parts)

                    if ok:
                        with self._history_lock:
                            for p in history_parts:
                                self.history.append_messages([
                                    ExtractedMessage(sender="self", text=p, top=0, left=0, right=0, ts=time.time())
                                ])
                        self.ui_status(f"✅ 已自动回复（{len(send_parts)} 条）并保存到本地历史")
                    else:
                        self.ui_status("⚠️ 回复生成了，但发送失败（多为焦点/前台/控件刷新）")
                finally:
                    self._busy_reply = False

        threading.Thread(target=worker, daemon=True).start()

    

    def _prepare_sticker_parts(self, parts: List[str]) -> Tuple[List[Any], List[str]]:
        send_parts: List[Any] = []
        history_parts: List[str] = []

        enabled = bool(getattr(self.cfg, "sticker_selector_enabled", False))
        api = (getattr(self.cfg, "sticker_selector_api", "") or "").strip()
        if not enabled or not api:
            if enabled and not api:
                self.ui_status("⚠️ StickerSelector 已启用但 API 地址为空，已按纯文本处理")
            for p in parts:
                text = (p or "").strip()
                if text:
                    send_parts.append(text)
                    history_parts.append(text)
            return send_parts, history_parts

        selector = StickerSelectorClient(api)
        k_cfg = getattr(self.cfg, "sticker_selector_k", 3) or 3
        series = getattr(self.cfg, "sticker_selector_series", "") or ""
        random_mode = bool(getattr(self.cfg, "sticker_selector_random", False))
        k_final = selector.normalize_k(k_cfg)
        if random_mode and k_final < 2:
            k_final = 2

        for part in parts:
            text = (part or "").strip()
            if not text:
                continue

            prompts = StickerSelectorClient.extract_prompts(text)
            if prompts:
                remaining = StickerSelectorClient.strip_prompts(text).strip()
                if remaining:
                    send_parts.append(remaining)
                    history_parts.append(remaining)

                for prompt in prompts:
                    prompt_clean = (prompt or "").strip()
                    if not prompt_clean:
                        continue

                    choice = selector.choose(prompt_clean, k_final, series, random_mode)
                    if choice.error:
                        self.ui_status(f"⚠️ 表情包获取失败：{choice.error}")
                        continue
                    if not choice.picked:
                        self.ui_status("⚠️ 表情包接口没有返回表情")
                        continue

                    picked = choice.picked
                    
                    if isinstance(picked, dict) and picked.get("url"):
                        send_parts.append({"sticker": picked})
                    else:
                        
                        send_parts.append(selector.format_item_message(picked))

                    
                    history_parts.append(f"<<<{prompt_clean}>>>")

                    pick_mode = "随机" if random_mode else "最高匹配"
                    self.ui_status(f"🎨 已选择表情包（mode={pick_mode}, k={choice.requested_k}）")
            else:
                send_parts.append(text)
                history_parts.append(text)

        if not send_parts:
            cleaned = [(p or "").strip() for p in parts if (p or "").strip()]
            return cleaned, cleaned

        return send_parts, history_parts

    def _split_reply(self, reply: str) -> List[str]:
        d = (self.cfg.split_delimiter or "<<<NEXT>>>").strip()
        if d and d in reply:
            parts = [p.strip() for p in reply.split(d) if p.strip()]
            return parts if parts else [reply.strip()]
        return [reply.strip()]

    def _calc_pause_for_part(self, text: str, idx: int) -> float:
        mult = float(self.cfg.split_speed_multiplier) if self.cfg.split_speed_multiplier else 1.0
        if mult <= 0:
            mult = 1.0

        char_time = float(self.cfg.split_char_time)
        base_pause = float(self.cfg.split_base_pause)

        est = base_pause + (len(text) * char_time) / mult
        est += idx * 0.12 / max(mult, 0.5)
        est += random.uniform(0.0, 0.35) / max(mult, 0.6)

        est = max(float(self.cfg.split_min_pause), min(float(self.cfg.split_max_pause), est))
        return est

    def _send_parts(self, parts: List[Any]) -> bool:
        if not parts:
            return False
        for i, part in enumerate(parts):
            if isinstance(part, dict) and part.get("sticker"):
                ok = self._send_sticker(part.get("sticker"))
            else:
                ok = self._send_one(str(part))
            if not ok:
                return False

            if i < len(parts) - 1:
                if isinstance(part, dict) and part.get("sticker"):
                    s_item = part.get("sticker") or {}
                    pause_text = (s_item.get("url") or "")
                else:
                    pause_text = str(part) if part is not None else ""
                time.sleep(self._calc_pause_for_part(pause_text, i))
        return True

    def _send_one(self, text: str) -> bool:
        with self._uia_lock:
            edit_ctrl = reacquire(self.bound_edit, self.tk_hwnd)
            btn_ctrl = reacquire(self.bound_button, self.tk_hwnd)
            if not edit_ctrl or not btn_ctrl:
                return False

            try:
                chat_hwnd = int(getattr(edit_ctrl, "NativeWindowHandle", 0) or 0)
            except Exception:
                chat_hwnd = 0

            r1 = try_input_text(edit_ctrl, text, hwnd=chat_hwnd)
            if r1 in ("failed", "blocked"):
                return False

            
            self._register_self_outgoing(text)

            r2 = try_click_button(btn_ctrl, hwnd=chat_hwnd)
            if r2 == "failed":
                try:
                    auto.SendKeys("{ENTER}", waitTime=0.01)
                    return True
                except Exception:
                    return False
            return True

    

    def _guess_ext(self, url: str, content_type: str, data: bytes) -> str:
        u = (url or "").lower()
        ct = (content_type or "").lower()

        m = re.search(r"\.(gif|png|webp|jpg|jpeg|bmp)(?:\?|#|$)", u)
        if m:
            return "." + m.group(1)

        if "image/gif" in ct:
            return ".gif"
        if "image/png" in ct:
            return ".png"
        if "image/webp" in ct:
            return ".webp"
        if "image/jpeg" in ct or "image/jpg" in ct:
            return ".jpg"

        if data[:6] in (b"GIF87a", b"GIF89a"):
            return ".gif"
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return ".png"
        if data[:2] == b"\xff\xd8":
            return ".jpg"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return ".webp"

        return ".png"

    def _copy_files_to_clipboard(self, paths: List[str]) -> bool:
        try:
            import win32clipboard
            import win32con

            abs_paths = [os.path.abspath(p) for p in paths if p and os.path.exists(p)]
            if not abs_paths:
                return False

            file_list = ("\0".join(abs_paths) + "\0\0").encode("utf-16le")

            
            
            
            dropfiles = struct.pack("<IiiII", 20, 0, 0, 0, 1) + file_list

            for _ in range(8):
                try:
                    win32clipboard.OpenClipboard()
                    break
                except Exception:
                    time.sleep(0.05)
            else:
                return False

            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_HDROP, dropfiles)
            finally:
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass

            return True
        except Exception as exc:
            self.ui_status(f"⚠️ 复制文件到剪贴板失败：{exc}")
            try:
                import win32clipboard  
                win32clipboard.CloseClipboard()
            except Exception:
                pass
            return False

    def _send_sticker(self, item: dict) -> bool:
        if not isinstance(item, dict):
            return False
        url = item.get("url")
        if not url:
            return False
        if not (url.startswith("http://") or url.startswith("https://")):
            base = getattr(self.cfg, "sticker_selector_api", "") or ""
            if base:
                url = base.rstrip("/") + "/" + str(url).lstrip("/")

        with self._uia_lock:
            edit_ctrl = reacquire(self.bound_edit, self.tk_hwnd)
            btn_ctrl = reacquire(self.bound_button, self.tk_hwnd)
            if not edit_ctrl or not btn_ctrl:
                return False

            try:
                chat_hwnd = int(getattr(edit_ctrl, "NativeWindowHandle", 0) or 0)
            except Exception:
                chat_hwnd = 0

            
            data = b""
            content_type = ""
            try:
                import requests
                r = requests.get(url, stream=True, timeout=10)
                r.raise_for_status()
                content_type = (r.headers.get("Content-Type", "") or "")
                data = r.content
            except Exception as exc:
                self.ui_status(f"⚠️ 下载表情失败：{exc}")
                return False

            
            try:
                desc = item.get("url") or ""
                self._register_self_outgoing(desc or url)
            except Exception:
                pass

            
            tmp_path = ""
            try:
                ext = self._guess_ext(url, content_type, data)
                tmp_dir = os.path.join(tempfile.gettempdir(), "StickerSelectorCache")
                os.makedirs(tmp_dir, exist_ok=True)
                tmp_path = os.path.join(tmp_dir, f"sticker_{uuid.uuid4().hex}{ext}")
                with open(tmp_path, "wb") as f:
                    f.write(data)
            except Exception as exc:
                self.ui_status(f"⚠️ 写入临时文件失败：{exc}")
                tmp_path = ""

            if tmp_path and os.path.exists(tmp_path):
                copied = self._copy_files_to_clipboard([tmp_path])
                if copied:
                    try:
                        try:
                            edit_ctrl.SetFocus()
                        except Exception:
                            pass
                        time.sleep(0.08)
                        auto.SendKeys("{CTRL}v", waitTime=0.02)
                        time.sleep(0.25)  

                        r2 = try_click_button(btn_ctrl, hwnd=chat_hwnd)
                        if r2 == "failed":
                            auto.SendKeys("{ENTER}", waitTime=0.01)
                        return True
                    except Exception as exc:
                        self.ui_status(f"⚠️ 文件粘贴发送失败，回退为静态位图：{exc}")

            
            try:
                from io import BytesIO
                from PIL import Image
                import win32clipboard
                import win32con

                bio = BytesIO()
                img = Image.open(BytesIO(data))
                try:
                    img.seek(0)  
                except Exception:
                    pass
                img = img.convert("RGB")  
                img.save(bio, format="BMP")
                bmp_data = bio.getvalue()[14:]

                for _ in range(6):
                    try:
                        win32clipboard.OpenClipboard()
                        break
                    except Exception:
                        time.sleep(0.05)
                else:
                    raise RuntimeError("OpenClipboard failed")

                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_DIB, bmp_data)
                finally:
                    try:
                        win32clipboard.CloseClipboard()
                    except Exception:
                        pass

                try:
                    edit_ctrl.SetFocus()
                except Exception:
                    pass
                time.sleep(0.06)
                auto.SendKeys("{CTRL}v", waitTime=0.02)
                time.sleep(0.10)

                r2 = try_click_button(btn_ctrl, hwnd=chat_hwnd)
                if r2 == "failed":
                    auto.SendKeys("{ENTER}", waitTime=0.01)
                return True
            except Exception as exc:
                self.ui_status(f"⚠️ 位图回退也失败：{exc}")

            
            try:
                self._register_self_outgoing(url)
                r1 = try_input_text(edit_ctrl, url, hwnd=chat_hwnd)
                if r1 in ("failed", "blocked"):
                    return False
                r2 = try_click_button(btn_ctrl, hwnd=chat_hwnd)
                if r2 == "failed":
                    auto.SendKeys("{ENTER}", waitTime=0.01)
                return True
            except Exception:
                return False
