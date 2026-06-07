"""Shared lightweight data structures used across the analysis modules."""

from dataclasses import dataclass


# A signal's stance. ``score`` is on a 0-100 scale where 50 is neutral,
# 100 is maximally bullish and 0 maximally bearish.
@dataclass
class Signal:
    name: str           # e.g. "RSI", "Golden Cross", "P/E"
    category: str       # "technical" or "fundamental"
    status: str         # "bullish" | "bearish" | "neutral" | "n/a"
    score: float        # 0-100 (50 = neutral); ignored when status == "n/a"
    detail: str         # human-readable explanation

    @property
    def available(self) -> bool:
        return self.status != "n/a"

    def signed_strength(self) -> float:
        """How far from neutral, signed. Used to rank the strongest reasons."""
        return self.score - 50.0
