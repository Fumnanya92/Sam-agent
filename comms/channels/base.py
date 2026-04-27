"""
Shared types for all channel adapters.
Mirrors Jarvis's ChannelAdapter interface from telegram.ts.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional


@dataclass
class ChannelMessage:
    id: str
    channel: str
    from_: str          # 'from' is a Python keyword — use from_
    text: str
    timestamp: float    # unix ms
    metadata: dict = field(default_factory=dict)


# Handler: receives an incoming message, returns a reply string (or "" to skip)
MessageHandler = Callable[[ChannelMessage], Awaitable[str]]


def split_text(text: str, max_length: int) -> list[str]:
    """Split long text at newlines/spaces to respect per-message char limits."""
    if len(text) <= max_length:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break
        idx = remaining.rfind("\n", 0, max_length)
        if idx < max_length // 2:
            idx = remaining.rfind(" ", 0, max_length)
        if idx < max_length // 2:
            idx = max_length
        chunks.append(remaining[:idx])
        remaining = remaining[idx:].lstrip()
    return chunks
