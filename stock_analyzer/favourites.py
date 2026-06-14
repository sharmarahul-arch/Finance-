"""Persistent favourites/watchlist with a pluggable backend.

Two storage modes:

* **local** (default) — a small JSON file. Persists across reruns/reconnections
  within a deployment, but resets on a Streamlit Cloud redeploy. Path overridable
  with ``STOCK_FAV_PATH``.
* **cloud** — a Supabase table (free tier). Durable across redeploys and shared
  across devices. Enabled by providing ``SUPABASE_URL`` + ``SUPABASE_KEY`` (via
  ``configure()`` from ``st.secrets``, or as env vars). See the README for setup.

Cloud calls always fall back to local storage on any error, so the app never
breaks if the network/credentials are unavailable.

Each favourite is a dict: ``{"symbol", "exchange", "name"}``.
"""

from __future__ import annotations

import json
import os
from typing import List, Dict, Optional

_PATH = os.environ.get("STOCK_FAV_PATH") or os.path.join(
    os.path.expanduser("~"), ".stock_analyzer_favourites.json"
)

# Runtime config for the optional cloud backend (set via configure() or env).
_CONFIG: Dict[str, Optional[str]] = {
    "supabase_url": None,
    "supabase_key": None,
    "table": "favourites",
    "user": "default",
}


def configure(supabase_url: Optional[str] = None, supabase_key: Optional[str] = None,
              table: Optional[str] = None, user: Optional[str] = None) -> None:
    """Set cloud-backend config (typically bridged from ``st.secrets``)."""
    if supabase_url:
        _CONFIG["supabase_url"] = supabase_url
    if supabase_key:
        _CONFIG["supabase_key"] = supabase_key
    if table:
        _CONFIG["table"] = table
    if user:
        _CONFIG["user"] = user


def _norm(exchange: Optional[str]) -> str:
    return (exchange or "NSE").upper()


# --------------------------------------------------------------------------- #
# Cloud backend (Supabase REST) — best-effort, lazy requests import.
# --------------------------------------------------------------------------- #
def _cloud_cfg():
    """Return (url, key, table, user) if a cloud backend is configured, else None."""
    url = _CONFIG["supabase_url"] or os.environ.get("SUPABASE_URL")
    key = _CONFIG["supabase_key"] or os.environ.get("SUPABASE_KEY")
    if url and key:
        table = _CONFIG["table"] or os.environ.get("STOCK_FAV_TABLE") or "favourites"
        user = _CONFIG["user"] or os.environ.get("STOCK_USER") or "default"
        return url.rstrip("/"), key, table, user
    return None


def storage_mode() -> str:
    return "cloud" if _cloud_cfg() else "local"


def _sb_headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _sb_read(cfg) -> List[Dict[str, str]]:
    import requests
    url, key, table, user = cfg
    resp = requests.get(
        f"{url}/rest/v1/{table}",
        headers=_sb_headers(key),
        params={"select": "symbol,exchange,name", "user_id": f"eq.{user}"},
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    return [
        {"symbol": str(r["symbol"]).upper(),
         "exchange": _norm(r.get("exchange")),
         "name": r.get("name") or r["symbol"]}
        for r in rows if r.get("symbol")
    ]


def _sb_add(cfg, fav: Dict[str, str]) -> None:
    import requests
    url, key, table, user = cfg
    headers = {**_sb_headers(key), "Prefer": "resolution=merge-duplicates"}
    body = {"user_id": user, "symbol": fav["symbol"],
            "exchange": fav["exchange"], "name": fav.get("name", "")}
    resp = requests.post(f"{url}/rest/v1/{table}", headers=headers, json=body, timeout=10)
    resp.raise_for_status()


def _sb_remove(cfg, symbol: str, exchange: str) -> None:
    import requests
    url, key, table, user = cfg
    resp = requests.delete(
        f"{url}/rest/v1/{table}",
        headers=_sb_headers(key),
        params={"user_id": f"eq.{user}", "symbol": f"eq.{symbol.upper()}",
                "exchange": f"eq.{_norm(exchange)}"},
        timeout=10,
    )
    resp.raise_for_status()


# --------------------------------------------------------------------------- #
# Local backend (JSON file)
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Public API — delegates to cloud when configured, else local; cloud failures
# transparently fall back to local so the app keeps working.
# --------------------------------------------------------------------------- #
def _read_all() -> List[Dict[str, str]]:
    cfg = _cloud_cfg()
    if cfg:
        try:
            return _sb_read(cfg)
        except Exception:
            pass
    return _load_raw()


def load_favourites(exchange: Optional[str] = None) -> List[Dict[str, str]]:
    """All favourites, optionally filtered to one exchange (sorted by name)."""
    favs = _read_all()
    if exchange is not None:
        favs = [f for f in favs if _norm(f.get("exchange")) == _norm(exchange)]
    return sorted(favs, key=lambda f: (f.get("name") or f["symbol"]).lower())


def is_favourite(symbol: str, exchange: str) -> bool:
    sym = symbol.upper()
    return any(
        f["symbol"].upper() == sym and _norm(f.get("exchange")) == _norm(exchange)
        for f in _read_all()
    )


def add_favourite(symbol: str, exchange: str, name: str = "") -> None:
    fav = {"symbol": symbol.upper(), "exchange": _norm(exchange), "name": name}
    cfg = _cloud_cfg()
    if cfg:
        try:
            _sb_add(cfg, fav)
            return
        except Exception:
            pass  # fall through to local
    favs = _load_raw()
    if not any(f["symbol"].upper() == fav["symbol"]
               and _norm(f.get("exchange")) == fav["exchange"] for f in favs):
        favs.append(fav)
        _save(favs)


def remove_favourite(symbol: str, exchange: str) -> None:
    cfg = _cloud_cfg()
    if cfg:
        try:
            _sb_remove(cfg, symbol, exchange)
            return
        except Exception:
            pass
    sym = symbol.upper()
    favs = [f for f in _load_raw()
            if not (f["symbol"].upper() == sym and _norm(f.get("exchange")) == _norm(exchange))]
    _save(favs)


def toggle_favourite(symbol: str, exchange: str, name: str = "") -> bool:
    """Add if absent, remove if present. Returns the new is-favourite state."""
    if is_favourite(symbol, exchange):
        remove_favourite(symbol, exchange)
        return False
    add_favourite(symbol, exchange, name)
    return True
