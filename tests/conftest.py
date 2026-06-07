"""Shared synthetic fixtures so tests never touch the network."""

import numpy as np
import pandas as pd
import pytest


def _ohlcv(close: np.ndarray) -> pd.DataFrame:
    """Build a plausible OHLCV frame from a close-price path."""
    n = len(close)
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    close = np.asarray(close, dtype=float)
    high = close * 1.01
    low = close * 0.99
    open_ = np.concatenate([[close[0]], close[:-1]])
    volume = np.full(n, 1_000_000.0)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


@pytest.fixture
def uptrend_df():
    # 300 sessions trending steadily up with mild noise.
    rng = np.random.default_rng(42)
    base = np.linspace(100, 200, 300)
    noise = rng.normal(0, 0.5, 300)
    return _ohlcv(base + noise)


@pytest.fixture
def downtrend_df():
    rng = np.random.default_rng(7)
    base = np.linspace(200, 100, 300)
    noise = rng.normal(0, 0.5, 300)
    return _ohlcv(base + noise)


@pytest.fixture
def strong_fundamentals():
    return {
        "trailingPE": 18.0,
        "priceToBook": 2.0,
        "pegRatio": 0.8,
        "returnOnEquity": 0.22,
        "profitMargins": 0.18,
        "revenueGrowth": 0.20,
        "earningsGrowth": 0.25,
        "debtToEquity": 30.0,        # 0.30x after normalization
        "dividendYield": 0.03,
        "marketCap": 5_000_000_000_0,
    }


@pytest.fixture
def weak_fundamentals():
    return {
        "trailingPE": 80.0,
        "priceToBook": 12.0,
        "pegRatio": 3.5,
        "returnOnEquity": -0.05,
        "profitMargins": -0.10,
        "revenueGrowth": -0.15,
        "earningsGrowth": -0.30,
        "debtToEquity": 250.0,       # 2.5x after normalization
        "dividendYield": 0.0,
        "marketCap": 1_000_000_00,
    }
