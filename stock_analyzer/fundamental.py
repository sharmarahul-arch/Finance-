"""Fundamental analysis: turn a yfinance ``.info`` dict into scored signals and an
aggregate fundamental score (0-100, 50 = neutral).

yfinance data is notoriously patchy, so every metric degrades gracefully to "n/a"
when the field is missing rather than crashing or skewing the score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from .config import FUNDAMENTAL_THRESHOLDS as T
from .models import Signal


@dataclass
class FundamentalResult:
    score: float
    signals: List[Signal] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)   # raw values for display


def _get(info: dict, *keys) -> Optional[float]:
    """First non-None numeric value among ``keys``; None otherwise."""
    for k in keys:
        v = info.get(k)
        if v is not None and isinstance(v, (int, float)) and not isinstance(v, bool):
            if not (isinstance(v, float) and np.isnan(v)):
                return float(v)
    return None


def evaluate(info: dict) -> FundamentalResult:
    info = info or {}
    signals: List[Signal] = []
    metrics: dict = {}

    # --- Valuation: P/E ----------------------------------------------------- #
    pe = _get(info, "trailingPE", "forwardPE")
    metrics["P/E"] = pe
    if pe is None:
        signals.append(Signal("P/E ratio", "fundamental", "n/a", 50, "P/E unavailable."))
    elif pe <= 0:
        signals.append(Signal("P/E ratio", "fundamental", "bearish", 30,
                              f"P/E {pe:.1f} — negative earnings."))
    elif pe <= T.pe_good:
        signals.append(Signal("P/E ratio", "fundamental", "bullish", 70,
                              f"P/E {pe:.1f} — reasonably valued."))
    elif pe <= T.pe_high:
        signals.append(Signal("P/E ratio", "fundamental", "neutral", 50,
                              f"P/E {pe:.1f} — moderately priced."))
    else:
        signals.append(Signal("P/E ratio", "fundamental", "bearish", 30,
                              f"P/E {pe:.1f} — expensive."))

    # --- Valuation: P/B ----------------------------------------------------- #
    pb = _get(info, "priceToBook")
    metrics["P/B"] = pb
    if pb is None:
        signals.append(Signal("P/B ratio", "fundamental", "n/a", 50, "P/B unavailable."))
    elif pb <= T.pb_good:
        signals.append(Signal("P/B ratio", "fundamental", "bullish", 65,
                              f"P/B {pb:.1f} — attractive book valuation."))
    else:
        signals.append(Signal("P/B ratio", "fundamental", "neutral", 45,
                              f"P/B {pb:.1f} — rich book valuation."))

    # --- Valuation: PEG ----------------------------------------------------- #
    peg = _get(info, "pegRatio", "trailingPegRatio")
    metrics["PEG"] = peg
    if peg is None:
        signals.append(Signal("PEG ratio", "fundamental", "n/a", 50, "PEG unavailable."))
    elif peg <= 0:
        signals.append(Signal("PEG ratio", "fundamental", "neutral", 50,
                              f"PEG {peg:.2f} — not meaningful."))
    elif peg <= T.peg_good:
        signals.append(Signal("PEG ratio", "fundamental", "bullish", 75,
                              f"PEG {peg:.2f} — growth cheaply priced."))
    elif peg <= T.peg_high:
        signals.append(Signal("PEG ratio", "fundamental", "neutral", 50,
                              f"PEG {peg:.2f} — fairly priced for growth."))
    else:
        signals.append(Signal("PEG ratio", "fundamental", "bearish", 30,
                              f"PEG {peg:.2f} — pricey for its growth."))

    # --- Profitability: ROE ------------------------------------------------- #
    roe = _get(info, "returnOnEquity")
    metrics["ROE"] = roe
    if roe is None:
        signals.append(Signal("ROE", "fundamental", "n/a", 50, "ROE unavailable."))
    elif roe >= T.roe_good:
        signals.append(Signal("ROE", "fundamental", "bullish", 78,
                              f"ROE {roe*100:.1f}% — high return on equity."))
    elif roe >= T.roe_weak:
        signals.append(Signal("ROE", "fundamental", "neutral", 50,
                              f"ROE {roe*100:.1f}% — modest."))
    else:
        signals.append(Signal("ROE", "fundamental", "bearish", 28,
                              f"ROE {roe*100:.1f}% — weak/negative."))

    # --- Profitability: margins -------------------------------------------- #
    margin = _get(info, "profitMargins", "operatingMargins")
    metrics["Net margin"] = margin
    if margin is None:
        signals.append(Signal("Profit margin", "fundamental", "n/a", 50, "Margin unavailable."))
    elif margin >= T.margin_good:
        signals.append(Signal("Profit margin", "fundamental", "bullish", 70,
                              f"Margin {margin*100:.1f}% — healthy profitability."))
    elif margin > 0:
        signals.append(Signal("Profit margin", "fundamental", "neutral", 50,
                              f"Margin {margin*100:.1f}% — thin."))
    else:
        signals.append(Signal("Profit margin", "fundamental", "bearish", 30,
                              f"Margin {margin*100:.1f}% — loss-making."))

    # --- Growth: revenue & earnings ---------------------------------------- #
    rev_growth = _get(info, "revenueGrowth")
    metrics["Revenue growth"] = rev_growth
    if rev_growth is None:
        signals.append(Signal("Revenue growth", "fundamental", "n/a", 50, "Revenue growth unavailable."))
    elif rev_growth >= T.revenue_growth_good:
        signals.append(Signal("Revenue growth", "fundamental", "bullish", 72,
                              f"Revenue growing {rev_growth*100:.1f}% YoY."))
    elif rev_growth >= 0:
        signals.append(Signal("Revenue growth", "fundamental", "neutral", 50,
                              f"Revenue growth {rev_growth*100:.1f}% YoY — sluggish."))
    else:
        signals.append(Signal("Revenue growth", "fundamental", "bearish", 30,
                              f"Revenue shrinking {rev_growth*100:.1f}% YoY."))

    earn_growth = _get(info, "earningsGrowth", "earningsQuarterlyGrowth")
    metrics["Earnings growth"] = earn_growth
    if earn_growth is None:
        signals.append(Signal("Earnings growth", "fundamental", "n/a", 50, "Earnings growth unavailable."))
    elif earn_growth >= T.earnings_growth_good:
        signals.append(Signal("Earnings growth", "fundamental", "bullish", 72,
                              f"Earnings growing {earn_growth*100:.1f}% YoY."))
    elif earn_growth >= 0:
        signals.append(Signal("Earnings growth", "fundamental", "neutral", 50,
                              f"Earnings growth {earn_growth*100:.1f}% YoY — flat."))
    else:
        signals.append(Signal("Earnings growth", "fundamental", "bearish", 30,
                              f"Earnings declining {earn_growth*100:.1f}% YoY."))

    # --- Leverage: debt-to-equity ------------------------------------------ #
    de = _get(info, "debtToEquity")
    # yfinance reports D/E as a percentage (e.g. 75.0 == 0.75x); normalize.
    if de is not None and de > 5:
        de = de / 100.0
    metrics["Debt/Equity"] = de
    if de is None:
        signals.append(Signal("Debt/Equity", "fundamental", "n/a", 50, "D/E unavailable."))
    elif de <= T.debt_equity_good:
        signals.append(Signal("Debt/Equity", "fundamental", "bullish", 68,
                              f"D/E {de:.2f} — healthy balance sheet."))
    elif de <= T.debt_equity_high:
        signals.append(Signal("Debt/Equity", "fundamental", "neutral", 45,
                              f"D/E {de:.2f} — moderate leverage."))
    else:
        signals.append(Signal("Debt/Equity", "fundamental", "bearish", 28,
                              f"D/E {de:.2f} — high leverage."))

    # --- Dividend yield ----------------------------------------------------- #
    dy = _get(info, "dividendYield")
    # yfinance has historically used both fraction (0.02) and percent (2.0); normalize.
    if dy is not None and dy > 1:
        dy = dy / 100.0
    metrics["Dividend yield"] = dy
    if dy is None:
        signals.append(Signal("Dividend yield", "fundamental", "n/a", 50, "Dividend yield unavailable."))
    elif dy >= T.dividend_yield_good:
        signals.append(Signal("Dividend yield", "fundamental", "bullish", 60,
                              f"Dividend yield {dy*100:.1f}% — income support."))
    else:
        signals.append(Signal("Dividend yield", "fundamental", "neutral", 50,
                              f"Dividend yield {dy*100:.1f}%."))

    metrics["Market cap"] = _get(info, "marketCap")

    score = _aggregate(signals)
    return FundamentalResult(score=score, signals=signals, metrics=metrics)


def _aggregate(signals: List[Signal]) -> float:
    usable = [s.score for s in signals if s.available]
    if not usable:
        return 50.0
    return float(np.mean(usable))


def analyze_fundamental(info: dict) -> FundamentalResult:
    return evaluate(info)
