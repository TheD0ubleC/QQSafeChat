
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal

Sender = Literal["self", "other", "unknown"]
MsgType = Literal["text", "system_time", "unknown"]

@dataclass
class BoundControl:
    expected_type: str  
    center_x: int
    center_y: int
    name: str = ""
    framework: str = ""
    automation_id: str = ""
    class_name: str = ""

@dataclass
class UiNodeText:
    text: str
    left: int
    top: int
    right: int
    bottom: int

@dataclass
class ExtractedMessage:
    sender: Sender
    text: str
    top: int
    left: int
    right: int
    
    debug_sender_name: Optional[str] = None
    msg_type: MsgType = "text"
    ts: float | None = None

    