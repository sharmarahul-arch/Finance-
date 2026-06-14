"""Central configuration: indicator parameters, fundamental thresholds, horizon profiles
and the verdict bands. Keeping these in one place makes the scoring logic easy to tune.
"""

from dataclasses import dataclass, field
from typing import Dict


# --------------------------------------------------------------------------- #
# Technical indicator parameters
# --------------------------------------------------------------------------- #
RSI_PERIOD = 14
SMA_SHORT = 20
SMA_MEDIUM = 50
SMA_LONG = 200
EMA_SHORT = 12
EMA_LONG = 26
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
ADX_PERIOD = 14
VOLUME_LOOKBACK = 20

# RSI thresholds
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# ADX: above this the trend is considered "real" / strong
ADX_TREND_THRESHOLD = 25


# --------------------------------------------------------------------------- #
# Fundamental thresholds (sensible defaults; tune to taste / sector)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FundamentalThresholds:
    pe_good: float = 25.0          # P/E below this is attractive
    pe_high: float = 45.0          # P/E above this is expensive
    pb_good: float = 3.0           # P/B below this is attractive
    peg_good: float = 1.0          # PEG < 1 is attractive
    peg_high: float = 2.0
    roe_good: float = 0.15         # ROE above 15% is strong
    roe_weak: float = 0.05
    debt_equity_good: float = 1.0  # D/E below this is healthy
    debt_equity_high: float = 2.0
    margin_good: float = 0.10      # net/operating margin above 10% is healthy
    revenue_growth_good: float = 0.10
    earnings_growth_good: float = 0.10
    dividend_yield_good: float = 0.02
    # From the playbook guide:
    current_ratio_good: float = 1.5      # >1.5 is comfortable
    debt_ebitda_good: float = 3.0        # <=3x manageable
    debt_ebitda_high: float = 4.0        # >4x risky
    payout_ratio_high: float = 0.80      # >80% may be unsustainable


FUNDAMENTAL_THRESHOLDS = FundamentalThresholds()


# --------------------------------------------------------------------------- #
# Horizon profiles -- the core of the "tailored" requirement.
#   * Short term  -> momentum/trend (technical) matters most.
#   * Long term   -> business quality/valuation (fundamental) matters most.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class HorizonProfile:
    key: str
    label: str
    technical_weight: float
    fundamental_weight: float
    default_period: str   # yfinance history period
    default_interval: str
    description: str
    # Fraction of the final composite given to news sentiment (when available).
    # The remaining (1 - news_weight) is split between technical & fundamental.
    news_weight: float = 0.0


HORIZONS: Dict[str, HorizonProfile] = {
    "short_term": HorizonProfile(
        key="short_term",
        label="Short term (trading / swing)",
        technical_weight=0.70,
        fundamental_weight=0.30,
        default_period="6mo",
        default_interval="1d",
        description="Emphasises price momentum, trend and entry timing.",
        news_weight=0.15,
    ),
    "long_term": HorizonProfile(
        key="long_term",
        label="Long term (investing)",
        technical_weight=0.30,
        fundamental_weight=0.70,
        default_period="5y",
        default_interval="1wk",
        description="Emphasises business quality, valuation and growth.",
        news_weight=0.05,
    ),
}


# --------------------------------------------------------------------------- #
# Verdict bands: composite score (0-100) -> human verdict.
# Ordered from highest threshold to lowest; first match wins.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class VerdictBand:
    min_score: float
    verdict: str
    color: str  # used by the Streamlit UI


VERDICT_BANDS = [
    VerdictBand(75, "Strong Buy", "#1a7e2e"),
    VerdictBand(60, "Buy", "#4caf50"),
    VerdictBand(40, "Hold", "#f0ad4e"),
    VerdictBand(25, "Sell", "#e8743b"),
    VerdictBand(0, "Strong Sell", "#c62828"),
]


def verdict_for_score(score: float) -> VerdictBand:
    """Return the VerdictBand whose ``min_score`` the score clears."""
    for band in VERDICT_BANDS:
        if score >= band.min_score:
            return band
    return VERDICT_BANDS[-1]
