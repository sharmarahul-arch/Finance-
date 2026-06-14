"""Stock analysis toolkit: technical + fundamental analysis with horizon-aware recommendations.

The package is intentionally UI-free so that the analysis logic can be unit-tested
and reused independently of the Streamlit front-end (``app.py``).
"""

from .recommendation import Recommendation, recommend
from .technical import TechnicalResult, analyze_technical
from .fundamental import FundamentalResult, analyze_fundamental
from .screener import ScreenResult, ScreenSummary, screen
from .backtest import BacktestResult, run_backtest
from .sentiment import SentimentResult, analyze_news, score_headline
from .config import HORIZONS

__all__ = [
    "Recommendation",
    "recommend",
    "TechnicalResult",
    "analyze_technical",
    "FundamentalResult",
    "analyze_fundamental",
    "ScreenResult",
    "ScreenSummary",
    "screen",
    "BacktestResult",
    "run_backtest",
    "SentimentResult",
    "analyze_news",
    "score_headline",
    "HORIZONS",
]
