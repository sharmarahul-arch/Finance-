"""Risk-management plan tests (offline, synthetic data)."""

import numpy as np
import pandas as pd

from stock_analyzer.risk import compute_risk_plan


def _ohlcv(close):
    n = len(close)
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    close = np.asarray(close, dtype=float)
    return pd.DataFrame(
        {"Open": close, "High": close * 1.02, "Low": close * 0.98,
         "Close": close, "Volume": [1_000_000.0] * n},
        index=idx,
    )


def test_no_capital_fails():
    plan = compute_risk_plan(_ohlcv(np.linspace(100, 120, 80)), account_size=0)
    assert plan.ok is False


def test_empty_data_fails():
    plan = compute_risk_plan(pd.DataFrame(), account_size=100000)
    assert plan.ok is False


def test_basic_plan_fields(uptrend_df):
    plan = compute_risk_plan(uptrend_df, account_size=100000, risk_pct=1.0, atr_mult=2.0)
    assert plan.ok
    assert plan.stop_loss < plan.entry          # long stop below entry
    assert plan.risk_per_share > 0
    assert plan.shares >= 0
    assert plan.stop_pct > 0


def test_capital_at_risk_respects_risk_pct(uptrend_df):
    # Capital at risk should not exceed account_size * risk_pct.
    account, risk_pct = 200000, 1.0
    plan = compute_risk_plan(uptrend_df, account_size=account, risk_pct=risk_pct)
    assert plan.capital_at_risk <= account * risk_pct / 100.0 + 1e-6


def test_position_capped_by_capital():
    # Tiny account, expensive stock with a tight stop -> capped by capital.
    df = _ohlcv(np.linspace(1000, 1010, 80))
    plan = compute_risk_plan(df, account_size=5000, risk_pct=2.0, atr_mult=1.0)
    assert plan.ok
    assert plan.position_value <= 5000 + 1e-6


def test_wider_atr_mult_gives_wider_stop(uptrend_df):
    tight = compute_risk_plan(uptrend_df, account_size=100000, atr_mult=1.0)
    wide = compute_risk_plan(uptrend_df, account_size=100000, atr_mult=3.0)
    assert wide.stop_loss < tight.stop_loss      # 3x ATR stop is further away
    assert wide.shares <= tight.shares           # wider stop -> smaller size
