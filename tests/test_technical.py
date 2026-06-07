"""Technical indicator + scoring tests (offline, synthetic data)."""

import numpy as np
import pandas as pd

from stock_analyzer import indicators as ind
from stock_analyzer.technical import compute_indicators, evaluate


def test_sma_matches_rolling_mean():
    s = pd.Series(range(1, 11), dtype=float)
    assert ind.sma(s, 3).iloc[-1] == np.mean([8, 9, 10])


def test_rsi_bounds():
    rng = np.random.default_rng(0)
    s = pd.Series(100 + np.cumsum(rng.normal(0, 1, 200)))
    r = ind.rsi(s, 14).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_rsi_all_gains_is_100():
    s = pd.Series(np.arange(1, 50, dtype=float))  # monotonically increasing
    assert ind.rsi(s, 14).dropna().iloc[-1] == 100.0


def test_compute_indicators_adds_columns(uptrend_df):
    out = compute_indicators(uptrend_df)
    for col in ["SMA20", "SMA50", "SMA200", "RSI", "MACD", "BB_UPPER", "ADX"]:
        assert col in out.columns


def test_uptrend_scores_higher_than_downtrend(uptrend_df, downtrend_df):
    up = evaluate(uptrend_df).score
    down = evaluate(downtrend_df).score
    assert up > 50 > down
    assert up > down


def test_uptrend_has_bullish_trend_signal(uptrend_df):
    res = evaluate(uptrend_df)
    trend = next(s for s in res.signals if s.name == "Trend (MA stack)")
    assert trend.status == "bullish"


def test_short_series_does_not_crash():
    # Only 10 rows -> long SMAs are NaN; should still return a neutral-ish result.
    df = pd.DataFrame({
        "Open": range(10), "High": range(1, 11), "Low": range(10),
        "Close": range(10), "Volume": [1000] * 10,
    }, index=pd.date_range("2023-01-01", periods=10))
    res = evaluate(df)
    assert 0 <= res.score <= 100
