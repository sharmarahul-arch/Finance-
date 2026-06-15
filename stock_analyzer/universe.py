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
_BUNDLED_SECTORS = os.path.join(os.path.dirname(__file__), "..", "data", "nse_stocks_sectors.csv")

# Public, current, comprehensive broker instrument dumps (no auth). These are the
# most reliable way to get *every* listed stock from a cloud host when NSE's own
# endpoint bot-blocks datacenter IPs.
KITE_INSTRUMENTS_URL = "https://api.kite.trade/instruments"
UPSTOX_NSE_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.csv.gz"
UPSTOX_BSE_URL = "https://assets.upstox.com/market-quote/instruments/exchange/BSE.csv.gz"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _download_nse_csv(timeout: float = 12.0) -> str:
    """Fetch NSE's full equity master, priming cookies to dodge its bot block."""
    import requests  # bundled transitively via yfinance

    s = requests.Session()
    s.headers.update(_HEADERS)
    try:
        s.get("https://www.nseindia.com/", timeout=timeout)  # prime cookies
    except Exception:
        pass
    resp = s.get(NSE_EQUITY_URL, headers={"Referer": "https://www.nseindia.com/"}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _download_kite(market: str = "NSE", timeout: float = 25.0) -> List[Dict[str, str]]:
    """Zerodha's public instruments dump → equities for the given exchange."""
    import requests

    resp = requests.get(KITE_INSTRUMENTS_URL, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    rows: List[Dict[str, str]] = []
    for r in csv.DictReader(io.StringIO(resp.text)):
        if (r.get("segment") == market and r.get("instrument_type") == "EQ"
                and r.get("exchange") == market):
            sym = (r.get("tradingsymbol") or "").strip().upper()
            name = (r.get("name") or sym).strip()
            if sym:
                rows.append({"symbol": sym, "name": name or sym})
    return rows


def _download_upstox(market: str = "NSE", timeout: float = 25.0) -> List[Dict[str, str]]:
    """Upstox's public gzipped instruments dump → equities for the exchange."""
    import gzip
    import requests

    url = UPSTOX_BSE_URL if market.upper() == "BSE" else UPSTOX_NSE_URL
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    text = gzip.decompress(resp.content).decode("utf-8", "replace")
    seg = f"{market.upper()}_EQ"
    rows: List[Dict[str, str]] = []
    for r in csv.DictReader(io.StringIO(text)):
        itype = (r.get("instrument_type") or "").upper()
        exch = (r.get("exchange") or "").upper()
        if itype == "EQ" and exch in (seg, market.upper()):
            sym = (r.get("tradingsymbol") or "").strip().upper()
            name = (r.get("name") or sym).strip()
            if sym:
                rows.append({"symbol": sym, "name": name or sym})
    return rows


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

    ``market`` is "NSE" or "BSE". Tries several public live sources in order so the
    *complete* current list loads on a normal host, then caches per market. Falls
    back to the bundled list if every source fails (e.g. fully offline).
    """
    market = (market or "NSE").upper()
    rows: List[Dict[str, str]] = []

    if prefer_live:
        # Ordered source chain: the first that returns a sizeable list wins.
        if market == "BSE":
            sources = [lambda: _download_kite("BSE"),
                       lambda: _download_upstox("BSE"),
                       _download_bse]
        else:
            sources = [lambda: _parse_nse_csv(_download_nse_csv()),
                       lambda: _download_kite("NSE"),
                       lambda: _download_upstox("NSE")]
        for fetch in sources:
            try:
                got = fetch()
            except Exception:
                got = []
            if got and len(got) >= 50:   # ignore truncated/garbage responses
                rows = got
                break

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


def curated_universe() -> List[Dict[str, str]]:
    """Sector-tagged pool of large, liquid, well-known names for the Top Picks scan.

    Each row is ``{"symbol", "name", "sector"}``. Reads the bundled sector dataset
    (so scans can be filtered sector-wise); falls back to the plain bundled list
    (sector "Other") if that file is missing. A fast, relevant candidate pool —
    scanning the full live list would be slow and include illiquid micro-caps.
    """
    rows: List[Dict[str, str]] = []
    seen = set()
    try:
        with open(os.path.normpath(_BUNDLED_SECTORS), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                sym = (r.get("symbol") or "").strip().upper()
                if sym and sym not in seen:
                    seen.add(sym)
                    rows.append({
                        "symbol": sym,
                        "name": (r.get("name") or sym).strip(),
                        "sector": (r.get("sector") or "Other").strip(),
                    })
    except OSError:
        rows = []

    if not rows:  # fallback: bundled list without sectors
        for r in _load_bundled():
            rows.append({**r, "sector": "Other"})

    rows.sort(key=lambda r: (r["sector"].lower(), r["name"].lower()))
    return rows


def curated_sectors() -> List[str]:
    """Sorted list of distinct sectors in the curated pool."""
    return sorted({r["sector"] for r in curated_universe()})


def search(query: str, market: str = "NSE", limit: int = 50) -> List[Dict[str, str]]:
    """Simple case-insensitive substring search over symbol and name."""
    q = (query or "").strip().lower()
    universe = load_universe(market)
    if not q:
        return universe[:limit]
    hits = [r for r in universe if q in r["symbol"].lower() or q in r["name"].lower()]
    return hits[:limit]
