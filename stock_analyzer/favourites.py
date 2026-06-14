"""Persistent favourites/watchlist, stored as a small JSON file.

Persists across reruns and reconnections within a deployment. The location can be
overridden with the ``STOCK_FAV_PATH`` env var. All writes degrade gracefully on a
read-only filesystem (favourites simply won't persist rather than crashing).

Each favourite is a dict: ``{"symbol", "exchange", "name"}``.
"""

from __future__ import annotations

import json
import os
from typing import List, Dict, Optional

_PATH = os.environ.get("STOCK_FAV_PATH") or os.path.join(
    os.path.expanduser("~"), ".stock_analyzer_favourites.json"
)


def _norm(exchange: Optional[str]) -> str:
    return (exchange or "NSE").upper()


def _load_raw() -> List[Dict[str, str]]:
    try:
        with open(_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict) and d.get("symbol")]
    except (OSError, json.JSONDecodeError):
        pass
    return []


def _save(favs: List[Dict[str, str]]) -> bool:
    try:
        directory = os.path.dirname(_PATH)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(_PATH, "w", encoding="utf-8") as fh:
            json.dump(favs, fh, indent=2)
        return True
    except OSError:
        return False


def load_favourites(exchange: Optional[str] = None) -> List[Dict[str, str]]:
    """All favourites, optionally filtered to one exchange (sorted by name)."""
    favs = _load_raw()
    if exchange is not None:
        favs = [f for f in favs if _norm(f.get("exchange")) == _norm(exchange)]
    return sorted(favs, key=lambda f: (f.get("name") or f["symbol"]).lower())


def is_favourite(symbol: str, exchange: str) -> bool:
    sym = symbol.upper()
    return any(
        f["symbol"].upper() == sym and _norm(f.get("exchange")) == _norm(exchange)
        for f in _load_raw()
    )


def add_favourite(symbol: str, exchange: str, name: str = "") -> List[Dict[str, str]]:
    favs = _load_raw()
    if not is_favourite(symbol, exchange):
        favs.append({"symbol": symbol.upper(), "exchange": _norm(exchange), "name": name})
        _save(favs)
    return favs


def remove_favourite(symbol: str, exchange: str) -> List[Dict[str, str]]:
    sym = symbol.upper()
    favs = [
        f for f in _load_raw()
        if not (f["symbol"].upper() == sym and _norm(f.get("exchange")) == _norm(exchange))
    ]
    _save(favs)
    return favs


def toggle_favourite(symbol: str, exchange: str, name: str = "") -> bool:
    """Add if absent, remove if present. Returns the new is-favourite state."""
    if is_favourite(symbol, exchange):
        remove_favourite(symbol, exchange)
        return False
    add_favourite(symbol, exchange, name)
    return True
