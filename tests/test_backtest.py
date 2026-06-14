"""Backtest tests (offline, synthetic price series)."""

import numpy as np
import pandas as pd

from stock_analyzer.backtest import run_backtest
from stock_analyzer.technical import compute_indicators, score_series


def _ohlcv(close):
    n = len(close)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = np.asarray(close, dtype=float)
    return pd.DataFrame(
        {"Open": close, "High": close * 1.01, "Low": close * 0.99,
         "Close": close, "Volume": [1_000_000.0] * n},
        index=idx,
    )


def test_insufficient_data_fails_gracefully():
    df = _ohlcv(np.linspace(100, 110, 20))
    res = run_backtest(df, min_bars=60)
    assert res.ok is False
    assert "enough" in res.message.lower()


def test_invalid_thresholds_rejected(uptrend_df):
    res = run_backtest(uptrend_df, buy_threshold=50, exit_threshold=60)
    assert res.ok is False


def test_uptrend_strategy_is_profitable(uptrend_df):
    res = run_backtest(uptrend_df)
    assert res.ok
    assert res.total_return > 0
    assert res.equity_curve.iloc[-1] > 1.0
    assert res.num_trades >= 1


def test_metrics_fields_present(uptrend_df):
    res = run_backtest(uptrend_df)
    assert res.ok
    for attr in ("total_return", "buy_hold_return", "cagr", "max_drawdown",
                 "exposure"):
        assert getattr(res, attr) is not None
    assert 0.0 <= res.exposure <= 1.0
    assert res.max_drawdown <= 0.0


def test_downtrend_limits_losses_vs_buy_hold(downtrend_df):
    # Going to cash on weakness should lose less than holding through the decline.
    res = run_backtest(downtrend_df)
    assert res.ok
    assert res.total_return >= res.buy_hold_return


def test_score_series_matches_evaluate_last_value(uptrend_df):
    # The per-bar score's final value should equal evaluate()'s aggregate score.
    from stock_analyzer.technical import evaluate
    enriched = compute_indicators(uptrend_df)
    series = score_series(enriched)
    agg = evaluate(uptrend_df).score
    assert abs(series.iloc[-1] - agg) < 1e-6
