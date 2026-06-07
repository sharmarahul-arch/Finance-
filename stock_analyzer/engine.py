"""End-to-end orchestration: ticker -> data -> analysis -> recommendation.

This is the single entry point the UI (or a CLI) should call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import data as data_mod
from .config import HORIZONS
from .fundamental import FundamentalResult, evaluate as eval_fundamental
from .recommendation import Recommendation, recommend
from .technical import TechnicalResult, evaluate as eval_technical


@dataclass
class AnalysisReport:
    meta: dict
    technical: TechnicalResult
    fundamental: FundamentalResult
    recommendation: Recommendation


def analyze_stock(
    symbol: str,
    exchange: str = "NSE",
    horizon: str = "long_term",
    period: Optional[str] = None,
    interval: Optional[str] = None,
) -> AnalysisReport:
    """Fetch data and run the full analysis pipeline for one ticker.

    Raises ``data.DataError`` on bad symbols / no price data.
    """
    if horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon '{horizon}'.")
    profile = HORIZONS[horizon]

    ticker = data_mod.normalize_ticker(symbol, exchange)
    price_df = data_mod.fetch_price_history(
        ticker,
        period=period or profile.default_period,
        interval=interval or profile.default_interval,
    )
    info = data_mod.fetch_fundamentals(ticker)
    meta = data_mod.get_company_meta(ticker, info)

    technical = eval_technical(price_df)
    fundamental = eval_fundamental(info)
    rec = recommend(technical, fundamental, horizon=horizon)

    return AnalysisReport(
        meta=meta,
        technical=technical,
        fundamental=fundamental,
        recommendation=rec,
    )
