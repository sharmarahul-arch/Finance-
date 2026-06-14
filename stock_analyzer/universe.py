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
# BSE active-equity list (JSON). SCRIP_ID is the alphabetic trading symbol that
# Yahoo Finance accepts with a .BO suffix (e.g. RELIANCE.BO).
BSE_EQUITY_URL = (
    "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
    "?Group=&Scripcode=&industry=&segment=Equity&status=Active"
)
_BUNDLED = os.path.join(os.path.dirname(__file__), "..", "data", "nse_equities.csv")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,application/json,*/*",
}


def _download_nse_csv(timeout: float = 10.0) -> str:
    import requests  # bundled transitively via yfinance

    resp = requests.get(NSE_EQUITY_URL, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _download_bse(timeout: float = 10.0) -> List[Dict[str, str]]:
    import requests

    headers = {**_HEADERS, "Referer": "https://www.bseindia.com/"}
    resp = requests.get(BSE_EQUITY_URL, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    rows: List[Dict[str, str]] = []
    for r in data if isinstance(data, list) else []:
        sym = (r.get("SCRIP_ID") or "").strip()
        name = (r.get("Scrip_Name") or r.get("SCRIP_NAME") or sym).strip()
        if sym:
            rows.append({"symbol": sym.upper(), "name": name or sym})
    return rows


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


@lru_cache(maxsize=4)
def load_universe(market: str = "NSE", prefer_live: bool = True) -> List[Dict[str, str]]:
    """Return a sorted, de-duplicated list of ``{"symbol", "name"}`` for ``market``.

    ``market`` is "NSE" or "BSE". Cached per market for the process lifetime.
    Falls back to the bundled list (dual-listed large caps, valid on both
    exchanges) if the live download fails or returns nothing.
    """
    market = (market or "NSE").upper()
    rows: List[Dict[str, str]] = []
    if prefer_live:
        try:
            if market == "BSE":
                rows = _download_bse()
            else:
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


def search(query: str, market: str = "NSE", limit: int = 50) -> List[Dict[str, str]]:
    """Simple case-insensitive substring search over symbol and name."""
    q = (query or "").strip().lower()
    universe = load_universe(market)
    if not q:
        return universe[:limit]
    hits = [r for r in universe if q in r["symbol"].lower() or q in r["name"].lower()]
    return hits[:limit]
