"""Technical analysis: compute indicators on an OHLCV frame and turn them into
scored signals and an aggregate technical score (0-100, 50 = neutral)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

from . import config
from . import indicators as ind
from .models import Signal


@dataclass
class TechnicalResult:
    score: float                       # 0-100 aggregate (50 = neutral)
    signals: List[Signal] = field(default_factory=list)
    enriched: pd.DataFrame = None      # OHLCV + indicator columns (for charts)


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with indicator columns added."""
    out = df.copy()
    close = out["Close"]

    out["SMA20"] = ind.sma(close, config.SMA_SHORT)
    out["SMA50"] = ind.sma(close, config.SMA_MEDIUM)
    out["SMA200"] = ind.sma(close, config.SMA_LONG)
    out["EMA12"] = ind.ema(close, config.EMA_SHORT)
    out["EMA26"] = ind.ema(close, config.EMA_LONG)
    out["RSI"] = ind.rsi(close, config.RSI_PERIOD)

    macd_line, signal_line, hist = ind.macd(
        close, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL
    )
    out["MACD"] = macd_line
    out["MACD_SIGNAL"] = signal_line
    out["MACD_HIST"] = hist

    mid, upper, lower = ind.bollinger_bands(close, config.BOLLINGER_PERIOD, config.BOLLINGER_STD)
    out["BB_MID"], out["BB_UPPER"], out["BB_LOWER"] = mid, upper, lower

    if {"High", "Low"}.issubset(out.columns):
        out["ADX"] = ind.adx(out["High"], out["Low"], close, config.ADX_PERIOD)

    if "Volume" in out.columns:
        out["VOL_AVG"] = out["Volume"].rolling(config.VOLUME_LOOKBACK, min_periods=1).mean()

    return out


def _last_valid(series: pd.Series):
    """Return the last non-NaN value of a series, or None."""
    if series is None:
        return None
    s = series.dropna()
    return None if s.empty else s.iloc[-1]


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def evaluate(df: pd.DataFrame) -> TechnicalResult:
    """Compute indicators and derive scored signals."""
    enriched = compute_indicators(df)
    signals: List[Signal] = []

    close = _last_valid(enriched["Close"])
    sma50 = _last_valid(enriched["SMA50"])
    sma200 = _last_valid(enriched["SMA200"])
    rsi_val = _last_valid(enriched["RSI"])
    macd_val = _last_valid(enriched["MACD"])
    macd_sig = _last_valid(enriched["MACD_SIGNAL"])
    bb_upper = _last_valid(enriched["BB_UPPER"])
    bb_lower = _last_valid(enriched["BB_LOWER"])
    adx_val = _last_valid(enriched.get("ADX"))
    vol = _last_valid(enriched.get("Volume"))
    vol_avg = _last_valid(enriched.get("VOL_AVG"))

    # --- Trend: price vs SMA50 / SMA200 (golden/death cross) ---------------- #
    if close is not None and sma50 is not None and sma200 is not None:
        if close > sma50 > sma200:
            signals.append(Signal("Trend (MA stack)", "technical", "bullish", 85,
                                  "Price > 50-DMA > 200-DMA — established uptrend."))
        elif close < sma50 < sma200:
            signals.append(Signal("Trend (MA stack)", "technical", "bearish", 15,
                                  "Price < 50-DMA < 200-DMA — established downtrend."))
        elif close > sma200:
            signals.append(Signal("Trend (MA stack)", "technical", "bullish", 65,
                                  "Price above the 200-DMA — long-term trend up."))
        else:
            signals.append(Signal("Trend (MA stack)", "technical", "bearish", 35,
                                  "Price below the 200-DMA — long-term trend down."))

    # Golden / death cross (50 vs 200)
    if sma50 is not None and sma200 is not None:
        if sma50 > sma200:
            signals.append(Signal("Golden/Death cross", "technical", "bullish", 70,
                                  "50-DMA above 200-DMA (golden-cross regime)."))
        else:
            signals.append(Signal("Golden/Death cross", "technical", "bearish", 30,
                                  "50-DMA below 200-DMA (death-cross regime)."))

    # --- Momentum: RSI ------------------------------------------------------ #
    if rsi_val is not None:
        if rsi_val < config.RSI_OVERSOLD:
            signals.append(Signal("RSI", "technical", "bullish", 75,
                                  f"RSI {rsi_val:.0f} — oversold, potential bounce."))
        elif rsi_val > config.RSI_OVERBOUGHT:
            signals.append(Signal("RSI", "technical", "bearish", 25,
                                  f"RSI {rsi_val:.0f} — overbought, pullback risk."))
        else:
            # Map 30-70 onto a mild 40-60 score (above 50 = mild momentum).
            score = 40 + (rsi_val - config.RSI_OVERSOLD) / (
                config.RSI_OVERBOUGHT - config.RSI_OVERSOLD
            ) * 20
            signals.append(Signal("RSI", "technical", "neutral", _clamp(score),
                                  f"RSI {rsi_val:.0f} — neutral momentum."))

    # --- Momentum: MACD ----------------------------------------------------- #
    if macd_val is not None and macd_sig is not None:
        if macd_val > macd_sig:
            signals.append(Signal("MACD", "technical", "bullish", 70,
                                  "MACD above its signal line — bullish momentum."))
        else:
            signals.append(Signal("MACD", "technical", "bearish", 30,
                                  "MACD below its signal line — bearish momentum."))

    # --- Volatility: Bollinger position ------------------------------------- #
    if close is not None and bb_upper is not None and bb_lower is not None:
        if close <= bb_lower:
            signals.append(Signal("Bollinger Bands", "technical", "bullish", 65,
                                  "Price at/below lower band — stretched low."))
        elif close >= bb_upper:
            signals.append(Signal("Bollinger Bands", "technical", "bearish", 35,
                                  "Price at/above upper band — stretched high."))
        else:
            signals.append(Signal("Bollinger Bands", "technical", "neutral", 50,
                                  "Price within the Bollinger bands."))

    # --- Trend strength: ADX (modifier, scored near neutral) ---------------- #
    if adx_val is not None:
        if adx_val >= config.ADX_TREND_THRESHOLD:
            signals.append(Signal("ADX (trend strength)", "technical", "neutral", 55,
                                  f"ADX {adx_val:.0f} — trend is strong/reliable."))
        else:
            signals.append(Signal("ADX (trend strength)", "technical", "neutral", 45,
                                  f"ADX {adx_val:.0f} — weak/range-bound trend."))

    # --- Volume confirmation ------------------------------------------------ #
    if vol is not None and vol_avg is not None and vol_avg > 0:
        ratio = vol / vol_avg
        if ratio >= 1.5:
            signals.append(Signal("Volume", "technical", "neutral", 58,
                                  f"Volume {ratio:.1f}x its 20-day average — strong participation."))
        elif ratio <= 0.5:
            signals.append(Signal("Volume", "technical", "neutral", 45,
                                  f"Volume {ratio:.1f}x average — thin participation."))

    score = _aggregate(signals)
    return TechnicalResult(score=score, signals=signals, enriched=enriched)


def _aggregate(signals: List[Signal]) -> float:
    """Average of available signal scores; 50 (neutral) when nothing is available."""
    usable = [s.score for s in signals if s.available]
    if not usable:
        return 50.0
    return float(np.mean(usable))


# Public convenience alias matching the package __init__ export.
def analyze_technical(df: pd.DataFrame) -> TechnicalResult:
    return evaluate(df)
