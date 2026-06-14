"""Lightweight, dependency-free news sentiment for finance headlines.

A curated finance lexicon with simple negation handling. Deterministic and offline
so it can be unit-tested without any model download or network call. Produces a
0-100 score (50 = neutral) compatible with the rest of the scoring engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from .models import Signal

# Decimal weight per matched term; magnitude reflects how strong the word is.
POSITIVE_TERMS = {
    "surge": 2.0, "surges": 2.0, "soar": 2.0, "soars": 2.0, "jump": 1.5, "jumps": 1.5,
    "rally": 1.5, "rallies": 1.5, "gain": 1.0, "gains": 1.0, "rise": 1.0, "rises": 1.0,
    "beat": 1.5, "beats": 1.5, "upgrade": 1.5, "upgrades": 1.5, "outperform": 1.5,
    "profit": 1.0, "profits": 1.0, "growth": 1.0, "record": 1.2, "strong": 1.0,
    "bullish": 2.0, "buy": 1.0, "boost": 1.2, "boosts": 1.2, "high": 0.8, "highs": 0.8,
    "expansion": 1.0, "dividend": 0.8, "approval": 1.0, "approved": 1.0, "wins": 1.0,
    "win": 1.0, "positive": 1.0, "robust": 1.0, "rebound": 1.2, "optimistic": 1.2,
}

NEGATIVE_TERMS = {
    "plunge": 2.0, "plunges": 2.0, "crash": 2.0, "crashes": 2.0, "slump": 1.5,
    "slumps": 1.5, "fall": 1.0, "falls": 1.0, "drop": 1.0, "drops": 1.0, "decline": 1.0,
    "declines": 1.0, "loss": 1.2, "losses": 1.2, "miss": 1.5, "misses": 1.5,
    "downgrade": 1.5, "downgrades": 1.5, "underperform": 1.5, "weak": 1.0, "bearish": 2.0,
    "sell": 1.0, "cut": 1.0, "cuts": 1.0, "warning": 1.5, "warns": 1.5, "fraud": 2.5,
    "probe": 1.5, "lawsuit": 1.5, "default": 2.0, "debt": 0.8, "low": 0.8, "lows": 0.8,
    "negative": 1.0, "concern": 1.0, "concerns": 1.0, "risk": 0.8, "slowdown": 1.2,
    "layoff": 1.5, "layoffs": 1.5, "recall": 1.2, "scam": 2.5, "selloff": 1.8,
}

NEGATIONS = {"not", "no", "never", "without", "fails", "fail", "denies", "deny"}

_WORD_RE = re.compile(r"[a-z']+")


def score_headline(text: str) -> float:
    """Return a sentiment polarity for one headline in roughly [-1, 1]."""
    if not text:
        return 0.0
    words = _WORD_RE.findall(text.lower())
    if not words:
        return 0.0

    raw = 0.0
    for i, w in enumerate(words):
        weight = POSITIVE_TERMS.get(w, 0.0) - NEGATIVE_TERMS.get(w, 0.0)
        if weight == 0.0:
            continue
        # Flip polarity if the previous word negates it.
        if i > 0 and words[i - 1] in NEGATIONS:
            weight = -weight
        raw += weight

    # Squash to [-1, 1] so a single strong word doesn't dominate.
    return max(-1.0, min(1.0, raw / 3.0))


@dataclass
class SentimentResult:
    score: float                       # 0-100 (50 = neutral)
    headline_count: int = 0
    signal: Signal = None
    per_headline: List[dict] = field(default_factory=list)


def analyze_news(headlines: List[str]) -> SentimentResult:
    """Aggregate headline sentiment into a 0-100 score and an explanatory Signal."""
    headlines = [h for h in (headlines or []) if h and h.strip()]
    if not headlines:
        sig = Signal("News sentiment", "news", "n/a", 50.0, "No recent headlines found.")
        return SentimentResult(score=50.0, headline_count=0, signal=sig)

    polarities = [score_headline(h) for h in headlines]
    avg = sum(polarities) / len(polarities)
    score = 50.0 + avg * 50.0  # map [-1,1] -> [0,100]

    if avg > 0.15:
        status, label = "bullish", "positive"
    elif avg < -0.15:
        status, label = "bearish", "negative"
    else:
        status, label = "neutral", "mixed/neutral"

    sig = Signal(
        "News sentiment", "news", status, round(score, 1),
        f"{len(headlines)} recent headlines — {label} tone.",
    )
    per = [{"headline": h, "polarity": round(p, 2)} for h, p in zip(headlines, polarities)]
    return SentimentResult(
        score=round(score, 1), headline_count=len(headlines), signal=sig, per_headline=per
    )
