"""Backtest the technical signals.

Strategy (long-only, no leverage): go long when the per-bar technical score rises
to ``buy_threshold`` and exit to cash when it falls to ``exit_threshold``. To avoid
look-ahead bias, a position decided on bar *t* is entered/exited at bar *t+1*'s close
(i.e. returns are driven by the previous bar's position).

Performance is compared against a simple buy-and-hold of the same stock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from .technical import compute_indicators, score_series

TRADING_DAYS = 252


@dataclass
class Trade:
    entry_date: str
    exit_date: Optional[str]
    entry_price: float
    exit_price: Optional[float]
    return_pct: Optional[float]   # decimal, e.g. 0.12 == +12%


@dataclass
class BacktestResult:
    ok: bool
    message: str = ""
    # Strategy metrics (decimals; None when not computable)
    total_return: Optional[float] = None
    buy_hold_return: Optional[float] = None
    cagr: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe: Optional[float] = None
    win_rate: Optional[float] = None
    num_trades: int = 0
    exposure: Optional[float] = None        # fraction of time in the market
    equity_curve: pd.Series = None          # strategy cumulative growth (starts at 1.0)
    buy_hold_curve: pd.Series = None
    trades: List[Trade] = field(default_factory=list)


def _max_drawdown(curve: pd.Series) -> float:
    running_max = curve.cummax()
    drawdown = curve / running_max - 1.0
    return float(drawdown.min())


def run_backtest(
    df: pd.DataFrame,
    buy_threshold: float = 60.0,
    exit_threshold: float = 45.0,
    min_bars: int = 60,
) -> BacktestResult:
    """Run the signal backtest on an OHLCV frame.

    Returns a :class:`BacktestResult`; ``ok=False`` (with a message) when there is
    not enough data to produce a meaningful test.
    """
    if df is None or df.empty or len(df) < min_bars:
        return BacktestResult(ok=False, message="Not enough price history to backtest.")
    if exit_threshold >= buy_threshold:
        return BacktestResult(ok=False, message="exit_threshold must be below buy_threshold.")

    enriched = compute_indicators(df)
    score = score_series(enriched)
    close = enriched["Close"].astype(float)

    # Target position: 1 when score >= buy, 0 when score <= exit, hold otherwise.
    target = pd.Series(np.nan, index=score.index)
    target[score >= buy_threshold] = 1.0
    target[score <= exit_threshold] = 0.0
    position = target.ffill().fillna(0.0)

    # No look-ahead: yesterday's position earns today's return.
    returns = close.pct_change().fillna(0.0)
    strat_returns = position.shift(1).fillna(0.0) * returns

    equity = (1.0 + strat_returns).cumprod()
    buy_hold = (1.0 + returns).cumprod()

    total_return = float(equity.iloc[-1] - 1.0)
    buy_hold_return = float(buy_hold.iloc[-1] - 1.0)

    # Annualised figures based on actual calendar span.
    span_days = max((equity.index[-1] - equity.index[0]).days, 1)
    years = span_days / 365.25
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 else None

    std = strat_returns.std()
    sharpe = float(strat_returns.mean() / std * np.sqrt(TRADING_DAYS)) if std and std > 0 else None

    max_dd = _max_drawdown(equity)
    exposure = float((position > 0).mean())

    trades = _extract_trades(position, close)
    wins = [t for t in trades if t.return_pct is not None and t.return_pct > 0]
    closed = [t for t in trades if t.return_pct is not None]
    win_rate = (len(wins) / len(closed)) if closed else None

    return BacktestResult(
        ok=True,
        total_return=total_return,
        buy_hold_return=buy_hold_return,
        cagr=cagr,
        max_drawdown=max_dd,
        sharpe=sharpe,
        win_rate=win_rate,
        num_trades=len(trades),
        exposure=exposure,
        equity_curve=equity,
        buy_hold_curve=buy_hold,
        trades=trades,
    )


def _extract_trades(position: pd.Series, close: pd.Series) -> List[Trade]:
    """Turn a 0/1 position series into discrete trades (entered/exited next bar)."""
    trades: List[Trade] = []
    prev = 0.0
    entry_idx = None
    idx = position.index

    for i in range(len(position)):
        cur = position.iloc[i]
        # Entry happens on the bar after the signal -> fill at next available close.
        if prev == 0.0 and cur == 1.0:
            fill = min(i + 1, len(position) - 1)
            entry_idx = fill
        elif prev == 1.0 and cur == 0.0 and entry_idx is not None:
            fill = min(i + 1, len(position) - 1)
            ep = float(close.iloc[entry_idx])
            xp = float(close.iloc[fill])
            trades.append(Trade(
                entry_date=str(idx[entry_idx].date()),
                exit_date=str(idx[fill].date()),
                entry_price=ep,
                exit_price=xp,
                return_pct=(xp / ep - 1.0) if ep else None,
            ))
            entry_idx = None
        prev = cur

    # Position still open at the end -> mark-to-market against the last close.
    if entry_idx is not None:
        ep = float(close.iloc[entry_idx])
        xp = float(close.iloc[-1])
        trades.append(Trade(
            entry_date=str(idx[entry_idx].date()),
            exit_date=None,
            entry_price=ep,
            exit_price=xp,
            return_pct=(xp / ep - 1.0) if ep else None,
        ))

    return trades
