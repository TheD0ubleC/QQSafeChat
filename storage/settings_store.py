
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class OpenAISettings:
    provider: str = "mock"  # 可选值: mock, openai, siliconflow
    api_key: str = "$OPENAI_API_KEY"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4.1-mini"
    temperature: float = 0.6

    
    system_prompt: str = "你是一个友好、简洁、不过度热情的聊天助手。"
    user_template: str = (
        "你是一个聊天助手。下面是聊天上下文（可能包含多行文件信息，已经合并成一个气泡）。\n"
        "请你只对“对方”最新消息进行简短自然回复，不要复述上下文。\n\n"
        "【聊天上下文】\n"
        "{history}\n\n"
        "【对方最新消息】\n"
        "{incoming}\n\n"
        "【你的回复】"
    )


class SettingsStore:
    def __init__(self, path: str):
        self.path = path
        self.settings = OpenAISettings()
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for k, v in data.items():
                if hasattr(self.settings, k):
                    setattr(self.settings, k, v)
        except Exception:
            pass

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        except Exception:
            pass
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(asdict(self.settings), f, ensure_ascii=False, indent=2)
        except Exception:
            pass
