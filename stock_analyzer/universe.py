"""The tradable stock universe (NSE) for the searchable picker.

Tries to pull the canonical, full NSE equity list from NSE's public archive so the
app offers *every* listed stock (like Groww/Zerodha search). If that download is
unavailable (offline / sandboxed), it falls back to a bundled curated list of the
most-traded names so the picker always works.
"""

from __future__ import annotations

import csv
import io
import os
from functools import lru_cache
from typing import List, Dict

# Canonical full NSE equity master (SYMBOL, NAME OF COMPANY, SERIES, ...).
NSE_EQUITY_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
_BUNDLED = os.path.join(os.path.dirname(__file__), "..", "data", "nse_equities.csv")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,*/*",
}


def _download_nse_csv(timeout: float = 10.0) -> str:
    import requests  # bundled transitively via yfinance

    resp = requests.get(NSE_EQUITY_URL, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _parse_nse_csv(text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    reader = csv.DictReader(io.StringIO(text))
    for r in reader:
        # NSE occasionally prefixes column names with a space.
        sym = (r.get("SYMBOL") or r.get(" SYMBOL") or "").strip()
        name = (r.get("NAME OF COMPANY") or r.get(" NAME OF COMPANY") or "").strip()
        series = (r.get(" SERIES") or r.get("SERIES") or "").strip()
        # Keep regular equity series only.
        if sym and series in ("", "EQ", "BE"):
            rows.append({"symbol": sym, "name": name or sym})
    return rows


def _load_bundled() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    try:
        with open(os.path.normpath(_BUNDLED), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                sym = (r.get("symbol") or "").strip()
                if sym:
                    rows.append({"symbol": sym, "name": (r.get("name") or sym).strip()})
    except OSError:
        pass
    return rows


@lru_cache(maxsize=1)
def load_universe(prefer_live: bool = True) -> List[Dict[str, str]]:
    """Return a sorted, de-duplicated list of ``{"symbol", "name"}`` for NSE.

    Cached for the process lifetime. Falls back to the bundled list if the live
    download fails or returns nothing.
    """
    rows: List[Dict[str, str]] = []
    if prefer_live:
        try:
            rows = _parse_nse_csv(_download_nse_csv())
        except Exception:
            rows = []
    if not rows:
        rows = _load_bundled()

    # De-duplicate by symbol, then sort by company name for nice search results.
    seen = set()
    unique = []
    for r in rows:
        key = r["symbol"].upper()
        if key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda r: r["name"].lower())
    return unique


def search(query: str, limit: int = 50) -> List[Dict[str, str]]:
    """Simple case-insensitive substring search over symbol and name."""
    q = (query or "").strip().lower()
    universe = load_universe()
    if not q:
        return universe[:limit]
    hits = [r for r in universe if q in r["symbol"].lower() or q in r["name"].lower()]
    return hits[:limit]
