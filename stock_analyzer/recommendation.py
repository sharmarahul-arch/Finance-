"""Combine technical + fundamental results into a single horizon-aware verdict."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from typing import Optional

from . import config
from .config import HORIZONS, verdict_for_score
from .fundamental import FundamentalResult
from .models import Signal
from .sentiment import SentimentResult
from .technical import TechnicalResult


@dataclass
class Recommendation:
    verdict: str                       # "Buy", "Hold", ...
    color: str                         # hex colour for the UI badge
    composite_score: float             # 0-100
    confidence: float                  # 0-100, how far from neutral / agreement
    horizon: str                       # "short_term" | "long_term"
    technical_score: float
    fundamental_score: float
    news_score: Optional[float] = None  # 0-100 when news was factored in
    bullish_reasons: List[str] = field(default_factory=list)
    bearish_reasons: List[str] = field(default_factory=list)


def _ranked_reasons(signals: List[Signal]):
    """Split available signals into bullish/bearish, each sorted by strength."""
    available = [s for s in signals if s.available and s.status != "neutral"]
    bullish = sorted(
        [s for s in available if s.signed_strength() > 0],
        key=lambda s: s.signed_strength(),
        reverse=True,
    )
    bearish = sorted(
        [s for s in available if s.signed_strength() < 0],
        key=lambda s: s.signed_strength(),
    )
    fmt = lambda s: f"{s.name}: {s.detail}"
    return [fmt(s) for s in bullish], [fmt(s) for s in bearish]


def recommend(
    technical: TechnicalResult,
    fundamental: FundamentalResult,
    horizon: str = "long_term",
    news: Optional[SentimentResult] = None,
    top_n_reasons: int = 6,
) -> Recommendation:
    if horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon '{horizon}'. Choose from {list(HORIZONS)}.")

    profile = HORIZONS[horizon]
    w_t = profile.technical_weight
    w_f = profile.fundamental_weight

    base = w_t * technical.score + w_f * fundamental.score

    # Blend in news sentiment only when we actually have headlines, so the default
    # (news=None) behaviour is unchanged and backward-compatible.
    news_score = None
    if news is not None and news.headline_count > 0:
        w_n = profile.news_weight
        composite = (1.0 - w_n) * base + w_n * news.score
        news_score = round(news.score, 1)
    else:
        composite = base

    band = verdict_for_score(composite)

    # Confidence: distance from neutral (50) scaled to 0-100.
    confidence = min(100.0, abs(composite - 50.0) * 2)

    all_signals = list(technical.signals) + list(fundamental.signals)
    if news is not None and news.signal is not None:
        all_signals.append(news.signal)
    bullish, bearish = _ranked_reasons(all_signals)

    return Recommendation(
        verdict=band.verdict,
        color=band.color,
        composite_score=round(composite, 1),
        confidence=round(confidence, 1),
        horizon=horizon,
        technical_score=round(technical.score, 1),
        fundamental_score=round(fundamental.score, 1),
        news_score=news_score,
        bullish_reasons=bullish[:top_n_reasons],
        bearish_reasons=bearish[:top_n_reasons],
    )
