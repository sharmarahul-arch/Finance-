"""End-to-end orchestration: ticker -> data -> analysis -> recommendation.

This is the single entry point the UI (or a CLI) should call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import data as data_mod
from .backtest import BacktestResult, run_backtest
from .config import HORIZONS
from .fundamental import FundamentalResult, evaluate as eval_fundamental
from .recommendation import Recommendation, recommend
from .sentiment import SentimentResult, analyze_news
from .technical import TechnicalResult, evaluate as eval_technical


@dataclass
class AnalysisReport:
    meta: dict
    technical: TechnicalResult
    fundamental: FundamentalResult
    recommendation: Recommendation
    news: Optional[SentimentResult] = None
    price_df: Optional["pd.DataFrame"] = None   # raw OHLCV, for backtesting/charts
    backtest: Optional[BacktestResult] = None


def analyze_stock(
    symbol: str,
    exchange: str = "NSE",
    horizon: str = "long_term",
    period: Optional[str] = None,
    interval: Optional[str] = None,
    include_news: bool = True,
    include_backtest: bool = False,
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
    quote = data_mod.fetch_fast_quote(ticker)
    meta = data_mod.get_company_meta(ticker, info, quote=quote)

    technical = eval_technical(price_df)
    fundamental = eval_fundamental(info)

    news = None
    if include_news:
        news = analyze_news(data_mod.fetch_news(ticker))

    rec = recommend(technical, fundamental, horizon=horizon, news=news)

    backtest = run_backtest(price_df) if include_backtest else None

    return AnalysisReport(
        meta=meta,
        technical=technical,
        fundamental=fundamental,
        recommendation=rec,
        news=news,
        price_df=price_df,
        backtest=backtest,
    )
