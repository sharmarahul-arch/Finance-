"""Risk management — position sizing, stop-loss and risk/reward.

Implements the playbook's "decide how much, and where you're wrong, *before*
entering" discipline: an ATR-based stop, a target from recent structure, the
resulting risk/reward, and a position size derived from the classic 1–2%
risk-per-trade rule.

This is an educational planning aid, not advice. It assumes a long (buy) setup.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import indicators as ind


@dataclass
class RiskPlan:
    ok: bool
    message: str = ""
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    atr: Optional[float] = None
    stop_pct: Optional[float] = None          # distance to stop, % of entry
    risk_per_share: Optional[float] = None
    reward_per_share: Optional[float] = None
    risk_reward: Optional[float] = None        # reward : risk multiple
    shares: Optional[int] = None
    position_value: Optional[float] = None
    capital_at_risk: Optional[float] = None
    capped_by_capital: bool = False            # position limited by available capital


def compute_risk_plan(
    price_df: pd.DataFrame,
    account_size: float,
    risk_pct: float = 1.0,
    atr_mult: float = 2.0,
    lookback: int = 20,
    resistance_lookback: int = 60,
    entry: Optional[float] = None,
) -> RiskPlan:
    """Build a risk plan for a long entry from an OHLCV frame.

    * stop-loss  = entry − atr_mult × ATR  (volatility-based)
    * target     = recent swing high (resistance); if none above entry, use a
                   default 2R target so risk/reward is still meaningful
    * shares     = (account_size × risk_pct%) ÷ risk-per-share, capped so the
                   position value never exceeds available capital
    """
    if price_df is None or price_df.empty or "Close" not in price_df:
        return RiskPlan(ok=False, message="No price data to build a risk plan.")
    if account_size is None or account_size <= 0:
        return RiskPlan(ok=False, message="Enter your capital to size a position.")

    high = price_df.get("High", price_df["Close"])
    low = price_df.get("Low", price_df["Close"])
    close = price_df["Close"].astype(float)

    entry = float(entry if entry is not None else close.iloc[-1])

    atr_series = ind.atr(high.astype(float), low.astype(float), close).dropna()
    if atr_series.empty or atr_series.iloc[-1] <= 0:
        # Fall back to a simple percentage stop if ATR isn't available yet.
        atr_val = entry * 0.05 / atr_mult
    else:
        atr_val = float(atr_series.iloc[-1])

    stop_loss = max(0.0, entry - atr_mult * atr_val)
    risk_per_share = entry - stop_loss
    if risk_per_share <= 0:
        return RiskPlan(ok=False, message="Computed stop is not below entry; cannot size.")

    # Target from recent resistance; otherwise default to a 2R objective.
    recent_high = float(high.tail(resistance_lookback).max())
    target = recent_high if recent_high > entry * 1.01 else entry + 2.0 * risk_per_share
    reward_per_share = target - entry
    risk_reward = reward_per_share / risk_per_share if risk_per_share else None

    capital_at_risk = account_size * (risk_pct / 100.0)
    shares = int(math.floor(capital_at_risk / risk_per_share))

    capped = False
    if shares * entry > account_size:
        shares = int(math.floor(account_size / entry))
        capped = True
    shares = max(shares, 0)

    return RiskPlan(
        ok=True,
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        target=round(target, 2),
        atr=round(atr_val, 2),
        stop_pct=round(risk_per_share / entry * 100.0, 2),
        risk_per_share=round(risk_per_share, 2),
        reward_per_share=round(reward_per_share, 2),
        risk_reward=round(risk_reward, 2) if risk_reward is not None else None,
        shares=shares,
        position_value=round(shares * entry, 2),
        capital_at_risk=round(min(capital_at_risk, shares * risk_per_share), 2),
        capped_by_capital=capped,
    )
