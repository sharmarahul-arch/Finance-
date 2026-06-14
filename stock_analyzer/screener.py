"""Multi-stock screener: analyse and rank a list of tickers by their
horizon-weighted composite score.

Pure-logic (UI-free). Fetches run in parallel because each ticker is I/O-bound
on the network. Per-ticker failures are captured rather than aborting the batch.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .config import HORIZONS
from .data import DataError
from .engine import analyze_stock

# Market-cap category thresholds (₹ crore). Rough but practical buckets.
CAP_LARGE_CR = 20000.0
CAP_MID_CR = 5000.0


def cap_bucket(market_cap: Optional[float]) -> Optional[str]:
    """Bucket an absolute market cap (₹) into Large / Mid / Small."""
    if not market_cap or market_cap <= 0:
        return None
    crore = market_cap / 1e7  # 1 crore = 1e7
    if crore >= CAP_LARGE_CR:
        return "Large"
    if crore >= CAP_MID_CR:
        return "Mid"
    return "Small"


@dataclass
class ScreenResult:
    symbol: str                         # as entered by the user
    ticker: Optional[str] = None        # normalized yfinance symbol
    name: Optional[str] = None
    price: Optional[float] = None
    currency: str = "INR"
    verdict: Optional[str] = None
    color: Optional[str] = None
    composite_score: Optional[float] = None
    technical_score: Optional[float] = None
    fundamental_score: Optional[float] = None
    change_pct: Optional[float] = None   # day change %
    sector: Optional[str] = None
    market_cap: Optional[float] = None
    cap_category: Optional[str] = None   # "Large" | "Mid" | "Small"
    top_reason: Optional[str] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class ScreenSummary:
    horizon: str
    exchange: str
    results: List[ScreenResult] = field(default_factory=list)

    @property
    def ranked(self) -> List[ScreenResult]:
        """Successful results sorted by composite score (desc); failures last."""
        return sorted(
            self.results,
            key=lambda r: (r.error is not None, -(r.composite_score or 0.0)),
        )

    @property
    def succeeded(self) -> List[ScreenResult]:
        return [r for r in self.results if r.ok]

    @property
    def failed(self) -> List[ScreenResult]:
        return [r for r in self.results if not r.ok]


def _analyze_one(symbol: str, exchange: str, horizon: str, analyze_fn: Callable) -> ScreenResult:
    symbol = (symbol or "").strip()
    if not symbol:
        return ScreenResult(symbol=symbol, error="Empty symbol.")
    try:
        report = analyze_fn(symbol, exchange=exchange, horizon=horizon)
    except DataError as exc:
        return ScreenResult(symbol=symbol, error=str(exc))
    except Exception as exc:  # noqa: BLE001 -- keep the batch alive
        return ScreenResult(symbol=symbol, error=f"{type(exc).__name__}: {exc}")

    rec = report.recommendation
    top_reason = rec.bullish_reasons[0] if rec.bullish_reasons else (
        rec.bearish_reasons[0] if rec.bearish_reasons else None
    )
    fund = getattr(report, "fundamental", None)
    market_cap = fund.metrics.get("Market cap") if fund is not None else None
    return ScreenResult(
        symbol=symbol,
        ticker=report.meta.get("ticker"),
        name=report.meta.get("name"),
        price=report.meta.get("price"),
        currency=report.meta.get("currency", "INR"),
        verdict=rec.verdict,
        color=rec.color,
        composite_score=rec.composite_score,
        technical_score=rec.technical_score,
        fundamental_score=rec.fundamental_score,
        change_pct=report.meta.get("change_pct"),
        sector=report.meta.get("sector"),
        market_cap=market_cap,
        cap_category=cap_bucket(market_cap),
        top_reason=top_reason,
    )


def screen(
    symbols: List[str],
    exchange: str = "NSE",
    horizon: str = "long_term",
    max_workers: int = 8,
    analyze_fn: Callable = analyze_stock,
) -> ScreenSummary:
    """Analyse ``symbols`` in parallel and return a ranked summary.

    ``analyze_fn`` is injectable so tests can supply a network-free stub; it must
    have the signature ``analyze_fn(symbol, exchange=..., horizon=...)``.
    """
    if horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon '{horizon}'. Choose from {list(HORIZONS)}.")

    # De-duplicate while preserving order; ignore blanks.
    seen = set()
    clean: List[str] = []
    for s in symbols:
        key = (s or "").strip().upper()
        if key and key not in seen:
            seen.add(key)
            clean.append(s.strip())

    results: List[ScreenResult] = []
    if not clean:
        return ScreenSummary(horizon=horizon, exchange=exchange, results=results)

    workers = max(1, min(max_workers, len(clean)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_analyze_one, sym, exchange, horizon, analyze_fn): sym
            for sym in clean
        }
        for fut in as_completed(futures):
            results.append(fut.result())

    return ScreenSummary(horizon=horizon, exchange=exchange, results=results)
