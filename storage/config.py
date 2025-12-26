
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
import os


def _ensure_dir(path: str):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


@dataclass
class AppConfig:
    
    config_path: str = "config.json"
    history_path: str = "history/history.jsonl"
    settings_path: str = "settings/openai.json"
    history_selected: str = ""
    auto_history_by_bind: bool = True

    
    poll_ms: int = 500
    snapshot_tail_keep: int = 500

    
    history_max_messages: int = 400

    
    auto_reply_enabled: bool = False

    
    reply_stop_seconds: float = 2.5

    
    reply_delay_mode: str = "fixed+random"

    
    reply_random_min: float = 0.3
    reply_random_max: float = 1.8

    
    split_delimiter: str = "<<<NEXT>>>"

    
    split_speed_multiplier: float = 1.0

    
    split_char_time: float = 0.06

    
    split_base_pause: float = 0.25

    
    split_min_pause: float = 0.35
    split_max_pause: float = 4.0

    
    sticker_selector_enabled: bool = False
    sticker_selector_api: str = ""
    sticker_selector_prompt: str = ""
    sticker_selector_k: int = 3
    sticker_selector_random: bool = False
    sticker_selector_series: str = ""

    
    persona_dir: str = "personas"
    persona_file: str = ""  

    @staticmethod
    def load(path: str = "config.json") -> "AppConfig":
        cfg = AppConfig()
        cfg.config_path = path
        if not os.path.exists(path):
            return cfg
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        except Exception:
            pass
        return cfg

    def save(self, path: str | None = None):
        path = path or self.config_path or "config.json"
        _ensure_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)
