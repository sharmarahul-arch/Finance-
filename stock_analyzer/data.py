"""Data access layer wrapping yfinance.

Kept free of any Streamlit imports so the package stays usable from the CLI / tests.
The Streamlit app wraps these functions with ``st.cache_data`` for caching.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

# yfinance is imported lazily inside functions so that the rest of the package
# (and the unit tests, which use synthetic data) does not require a network stack.


class DataError(Exception):
    """Raised when market data cannot be retrieved for a ticker."""


_EXCHANGE_SUFFIX = {
    "NSE": ".NS",
    "BSE": ".BO",
}


def normalize_ticker(symbol: str, exchange: str = "NSE") -> str:
    """Normalize a user-entered Indian ticker to a yfinance symbol.

    Examples:
        normalize_ticker("reliance")        -> "RELIANCE.NS"
        normalize_ticker("TCS", "BSE")       -> "TCS.BO"
        normalize_ticker("INFY.NS")          -> "INFY.NS"   (already suffixed)
        normalize_ticker("AAPL")  with US?   -> handled by caller; default is NSE
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        raise DataError("Empty ticker symbol.")

    # Already has an exchange suffix -> leave as-is.
    if "." in symbol:
        return symbol

    suffix = _EXCHANGE_SUFFIX.get(exchange.upper(), ".NS")
    return f"{symbol}{suffix}"


def fetch_price_history(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
) -> pd.DataFrame:
    """Return an OHLCV DataFrame for ``ticker``.

    Columns: Open, High, Low, Close, Volume (DatetimeIndex).
    Raises DataError if nothing comes back.
    """
    import yfinance as yf

    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
    except Exception as exc:  # network / yfinance internal errors
        raise DataError(f"Could not fetch price history for {ticker}: {exc}") from exc

    if df is None or df.empty:
        raise DataError(
            f"No price data returned for '{ticker}'. "
            "Check the symbol/exchange (Indian tickers use .NS for NSE, .BO for BSE)."
        )

    # Keep only the standard OHLCV columns and drop fully-empty rows.
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[keep].dropna(how="all")
    return df


def fetch_fundamentals(ticker: str) -> dict:
    """Return the yfinance ``.info`` dict (best-effort).

    yfinance frequently returns partial data; downstream code must tolerate
    missing/None keys. Returns an empty dict on hard failure rather than raising,
    so a stock with no fundamentals can still be analysed technically.
    """
    import yfinance as yf

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}
    return info


def fetch_news(ticker: str, limit: int = 10) -> list:
    """Return up to ``limit`` recent headline strings for ``ticker`` (best-effort).

    yfinance's news payload shape has varied over versions, so we probe the common
    locations for a title. Returns an empty list on any failure rather than raising,
    so the rest of the analysis still proceeds.
    """
    import yfinance as yf

    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        return []

    headlines = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        # Newer yfinance nests fields under "content".
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        title = item.get("title") or content.get("title")
        if title:
            headlines.append(str(title).strip())
        if len(headlines) >= limit:
            break
    return headlines


def get_company_meta(ticker: str, info: Optional[dict] = None) -> dict:
    """Return a small dict of display metadata: name, sector, price, currency."""
    if info is None:
        info = fetch_fundamentals(ticker)

    price = (
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
    )
    prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")

    change = change_pct = None
    if price is not None and prev_close:
        change = price - prev_close
        change_pct = (change / prev_close * 100.0) if prev_close else None

    return {
        "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector") or "—",
        "industry": info.get("industry") or "—",
        "price": price,
        "previous_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "currency": info.get("currency") or "INR",
        "ticker": ticker,
    }
