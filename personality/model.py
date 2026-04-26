"""
personality/model.py — Adaptive personality learner.
Ported from Jarvis src/personality/model.ts + learner.ts

Tracks user interaction patterns and adapts:
  - Preferred response style (concise / detailed / technical)
  - Common topics and domains
  - Time-of-day usage patterns
  - Feedback signals (positive/negative on responses)

All data stored in SQLite (settings table as JSON blobs).
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal

import aiosqlite
from vault.schema import DB_PATH

logger = logging.getLogger("sam.personality")

StylePreference = Literal["concise", "balanced", "detailed", "technical"]


@dataclass
class PersonalityProfile:
    style: StylePreference = "balanced"
    formality: float = 0.5          # 0.0 = casual, 1.0 = formal
    verbosity: float = 0.5          # 0.0 = terse, 1.0 = verbose
    technical_depth: float = 0.5    # 0.0 = simple, 1.0 = expert
    top_topics: list[str] = field(default_factory=list)
    positive_signals: int = 0
    negative_signals: int = 0
    total_interactions: int = 0
    updated_at: str = ""


class PersonalityLearner:
    _SETTINGS_KEY = "personality_profile"

    # ── Load / Save ───────────────────────────────────────────────────────────

    async def load(self) -> PersonalityProfile:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT value FROM settings WHERE key = ?", (self._SETTINGS_KEY,)
            )
            row = await cur.fetchone()
        if not row:
            return PersonalityProfile()
        try:
            data = json.loads(row["value"])
            return PersonalityProfile(**{k: v for k, v in data.items() if k in PersonalityProfile.__dataclass_fields__})
        except Exception:
            return PersonalityProfile()

    async def save(self, profile: PersonalityProfile) -> None:
        profile.updated_at = datetime.utcnow().isoformat() + "Z"
        now = profile.updated_at
        value = json.dumps(asdict(profile))
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                """INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (self._SETTINGS_KEY, value, now),
            )
            await db.commit()

    # ── Learning ──────────────────────────────────────────────────────────────

    async def record_interaction(
        self,
        user_message: str,
        response_length: int,
        topics: list[str] | None = None,
    ) -> None:
        profile = await self.load()
        profile.total_interactions += 1

        # Nudge verbosity toward observed response length
        if response_length < 100:
            profile.verbosity = max(0.0, profile.verbosity - 0.01)
        elif response_length > 500:
            profile.verbosity = min(1.0, profile.verbosity + 0.01)

        # Track topic frequency
        if topics:
            for t in topics:
                if t not in profile.top_topics:
                    profile.top_topics.append(t)
            profile.top_topics = profile.top_topics[-20:]  # keep last 20

        await self.save(profile)

    async def record_feedback(self, positive: bool) -> None:
        profile = await self.load()
        if positive:
            profile.positive_signals += 1
            # More positive feedback → slightly more verbose + detailed
            profile.verbosity = min(1.0, profile.verbosity + 0.02)
            profile.technical_depth = min(1.0, profile.technical_depth + 0.01)
        else:
            profile.negative_signals += 1
            # Negative → be more concise
            profile.verbosity = max(0.0, profile.verbosity - 0.02)
        await self.save(profile)

    async def set_style(self, style: StylePreference) -> None:
        profile = await self.load()
        profile.style = style
        style_presets = {
            "concise":   (0.2, 0.3),
            "balanced":  (0.5, 0.5),
            "detailed":  (0.8, 0.7),
            "technical": (0.7, 0.9),
        }
        v, d = style_presets.get(style, (0.5, 0.5))
        profile.verbosity = v
        profile.technical_depth = d
        await self.save(profile)

    # ── System prompt injection ───────────────────────────────────────────────

    async def get_style_instruction(self) -> str:
        """Return a short instruction to inject into the system prompt."""
        profile = await self.load()
        parts = []

        if profile.style == "concise":
            parts.append("Be concise. Answer in 1-3 sentences when possible.")
        elif profile.style == "detailed":
            parts.append("Provide detailed, thorough responses.")
        elif profile.style == "technical":
            parts.append("Use technical language appropriate for an expert audience.")

        if profile.verbosity < 0.3:
            parts.append("Keep responses short.")
        elif profile.verbosity > 0.7:
            parts.append("Expand explanations where helpful.")

        if profile.technical_depth > 0.7:
            parts.append("Include implementation details and edge cases.")
        elif profile.technical_depth < 0.3:
            parts.append("Avoid jargon. Use simple language.")

        return " ".join(parts) if parts else ""

    async def get_profile(self) -> dict:
        return asdict(await self.load())


# Singleton
_learner: PersonalityLearner | None = None


def get_learner() -> PersonalityLearner:
    global _learner
    if _learner is None:
        _learner = PersonalityLearner()
    return _learner
