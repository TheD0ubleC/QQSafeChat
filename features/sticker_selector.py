from __future__ import annotations

import json
import random
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:  
    import requests
except Exception:  
    requests = None


@dataclass
class StickerChoice:
    prompt: str
    items: List[Dict[str, Any]]
    meta: Dict[str, Any]
    requested_k: int
    picked: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class StickerSelectorClient:
    def __init__(self, base_url: str, max_k: int = 6):
        self.base_url = (base_url or "").rstrip("/")
        self.max_k = max(1, max_k)

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def normalize_k(self, k: int) -> int:
        try:
            v = int(k)
        except Exception:  
            v = 1
        v = max(1, v)
        return min(v, self.max_k)

    def _full_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def select(self, tags: str, k: int, series: str | None = None) -> StickerChoice:
        if not self.is_configured():
            return StickerChoice(prompt=tags, items=[], meta={}, requested_k=1, error="API 未配置")

        tags_clean = (tags or "").strip()
        if not tags_clean:
            return StickerChoice(prompt=tags, items=[], meta={}, requested_k=1, error="标签为空")

        k_final = self.normalize_k(k)
        params = {"tags": tags_clean, "k": k_final}
        if series:
            params["series"] = str(series).strip()

        url = f"{self.base_url}/api/select"

        try:
            if requests:
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
            else:
                query = urllib.parse.urlencode(params)
                with urllib.request.urlopen(f"{url}?{query}", timeout=10) as r:  
                    data = json.loads(r.read().decode("utf-8"))
        except Exception as exc:  
            return StickerChoice(prompt=tags_clean, items=[], meta={}, requested_k=k_final, error=str(exc))

        if not isinstance(data, dict):
            return StickerChoice(
                prompt=tags_clean,
                items=[],
                meta={},
                requested_k=k_final,
                error="响应格式异常",
            )

        items = data.get("items") if isinstance(data.get("items"), list) else []
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        return StickerChoice(prompt=tags_clean, items=items, meta=meta, requested_k=k_final)

    def pick_item(self, items: List[Dict[str, Any]], use_random: bool) -> Optional[Dict[str, Any]]:
        if not items:
            return None
        if use_random and len(items) > 1:
            return random.choice(items)
        return items[0]

    def choose(self, prompt: str, k: int, series: str | None, use_random: bool) -> StickerChoice:
        res = self.select(prompt, k, series)
        if res.error:
            return res
        res.picked = self.pick_item(res.items, use_random)
        return res

    def format_item_message(self, item: Dict[str, Any]) -> str:
        url = self._full_url(str(item.get("url") or "")) if item else ""
        tags = item.get("tags") or []
        tag_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
        raw_score = item.get("raw")
        fit_rate = item.get("fit_rate")
        series = item.get("series") or ""
        parts = [p for p in [f"url={url}" if url else "", f"tags={tag_str}" if tag_str else "", f"series={series}" if series else ""] if p]
        if raw_score is not None:
            parts.append(f"raw={raw_score}")
        if fit_rate is not None:
            parts.append(f"fit={fit_rate}")
        return " | ".join(parts) or url or tag_str or "(no sticker)"

    @staticmethod
    def extract_prompts(text: str) -> List[str]:
        return re.findall(r"<<<([^<>]+?)>>>", text) if text else []

    @staticmethod
    def strip_prompts(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"<<<[^<>]+?>>>", "", text)
