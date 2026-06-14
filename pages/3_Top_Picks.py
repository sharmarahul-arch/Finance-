"""Top Picks page — automatically scan a pool of liquid stocks and surface the
strongest Buy candidates, with market-cap and sector filters.

Fundamentals decide *what*, technicals decide *when* — this page does the "what"
discovery step for you, then you can open any pick on the analysis page.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from stock_analyzer import universe as universe_mod
from stock_analyzer.config import HORIZONS
from stock_analyzer.screener import screen

st.set_page_config(page_title="Top Picks — Stock Analyzer", page_icon="🏆", layout="wide")

BUY_VERDICTS = {"Buy", "Strong Buy"}
CAP_ORDER = ["Large", "Mid", "Small"]


@st.cache_data(ttl=900, show_spinner=False)
def _cached_scan(symbols: tuple, exchange: str, horizon: str):
    return screen(list(symbols), exchange=exchange, horizon=horizon, max_workers=8)


def _fmt_money(value, currency="INR"):
    if value is None:
        return "—"
    prefix = "₹" if currency == "INR" else ""
    try:
        return f"{prefix}{value:,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_cap(value):
    if not value:
        return "—"
    return f"₹{value/1e7:,.0f} Cr"


def _go_analyse(symbol: str, exch: str):
    """Pre-select the stock and jump to the main analysis page."""
    st.session_state["symbol"] = symbol
    st.session_state["exchange"] = exch
    if hasattr(st, "switch_page"):
        st.switch_page("app.py")
    else:  # very old Streamlit
        st.info(f"Selected {symbol}. Open the main analysis page from the sidebar.")


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
st.sidebar.title("🏆 Top Picks")
st.sidebar.caption("Auto-scan liquid stocks and rank the best Buys")

exchange = st.sidebar.selectbox("Exchange", ["NSE", "BSE"], index=0)
horizon_label = st.sidebar.radio(
    "Investment horizon",
    options=[HORIZONS["short_term"].label, HORIZONS["long_term"].label],
)
horizon = "short_term" if horizon_label == HORIZONS["short_term"].label else "long_term"
st.sidebar.caption(HORIZONS[horizon].description)

pool = universe_mod.curated_universe()
scan_n = st.sidebar.slider(
    "How many stocks to scan", min_value=10, max_value=len(pool),
    value=min(40, len(pool)), step=10,
    help="More = broader search but slower (each stock is a live fetch).",
)
run = st.sidebar.button("🔍 Find top picks", type="primary", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.warning(
    "**Disclaimer:** Educational tool, **not financial advice**. Rankings are "
    "heuristic — always do your own research."
)

# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
st.title("Top Stock Picks")
st.caption(
    "Scans a pool of large, liquid stocks with the same engine as the analysis page, "
    "then ranks them by the horizon-weighted Buy score. Filter by market-cap category "
    "and sector below."
)

if not run:
    st.info("Pick an exchange, horizon and scan size in the sidebar, then click "
            "**Find top picks**.")
    st.stop()

symbols = [r["symbol"] for r in pool][:scan_n]
with st.spinner(f"Scanning {len(symbols)} stocks ({exchange}, {HORIZONS[horizon].label})…"):
    summary = _cached_scan(tuple(symbols), exchange, horizon)

ok = summary.succeeded
if not ok:
    st.error("Could not analyse any stocks (data feed may be unavailable). Try again.")
    st.stop()

# --- Filters (applied to the already-scanned results — no re-fetch) --------- #
present_caps = [c for c in CAP_ORDER if any(r.cap_category == c for r in ok)]
sectors = sorted({r.sector for r in ok if r.sector and r.sector != "—"})

f1, f2, f3 = st.columns([1, 1, 1])
cap_filter = f1.multiselect("Market-cap category", CAP_ORDER,
                            default=present_caps or CAP_ORDER)
sector_filter = f2.multiselect("Sector", sectors, default=sectors)
buys_only = f3.toggle("Buy-rated only", value=True,
                      help="Show only stocks rated Buy or Strong Buy.")

filtered = [
    r for r in ok
    if (not cap_filter or r.cap_category in cap_filter or r.cap_category is None)
    and (not sector_filter or r.sector in sector_filter or not r.sector)
    and (not buys_only or r.verdict in BUY_VERDICTS)
]
filtered.sort(key=lambda r: -(r.composite_score or 0))

st.markdown(f"### 🏅 {len(filtered)} matching pick(s)")
if not filtered:
    st.info("No stocks match these filters. Loosen the filters or scan more stocks.")
    st.stop()

# --- Highlight the top 3 as cards ------------------------------------------- #
top = filtered[:3]
cols = st.columns(len(top))
for col, r in zip(cols, top):
    with col:
        col.markdown(
            f"<div style='padding:1rem;border-radius:12px;background:{r.color};color:white'>"
            f"<div style='font-size:0.8rem;opacity:0.9'>{r.cap_category or '—'} cap · {r.sector or '—'}</div>"
            f"<div style='font-size:1.3rem;font-weight:700'>{r.symbol}</div>"
            f"<div style='font-size:0.85rem'>{r.name or ''}</div>"
            f"<div style='font-size:1.6rem;font-weight:700;margin-top:.3rem'>{r.verdict}</div>"
            f"<div style='font-size:0.85rem'>Score {r.composite_score}/100</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if r.top_reason:
            st.caption(f"💡 {r.top_reason}")
        if col.button("📊 Open analysis", key=f"card_open_{r.symbol}",
                      use_container_width=True):
            _go_analyse(r.symbol, exchange)

# --- Clickable list — every pick opens the full analysis page --------------- #
st.markdown("### Open full analysis")
st.caption("Click any stock to open its full breakdown, charts and risk plan.")
for i, r in enumerate(filtered, start=1):
    day = "" if r.change_pct is None else f"  ·  {r.change_pct:+.2f}%"
    label = (f"{i}. {r.name or r.symbol}  ({r.symbol})  —  {r.verdict}  ·  "
             f"score {r.composite_score}  ·  {r.cap_category or '—'} cap{day}")
    if st.button(label, key=f"open_{r.symbol}", use_container_width=True):
        _go_analyse(r.symbol, exchange)

# --- Full ranked table ------------------------------------------------------ #
rows = [{
    "Rank": i,
    "Symbol": r.symbol,
    "Name": r.name,
    "Verdict": r.verdict,
    "Score": r.composite_score,
    "Cap": r.cap_category or "—",
    "Sector": r.sector or "—",
    "Day %": r.change_pct,
    "Price": _fmt_money(r.price, r.currency),
    "Why": r.top_reason or "—",
} for i, r in enumerate(filtered, start=1)]
df = pd.DataFrame(rows)

color_map = {r.verdict: r.color for r in filtered if r.verdict and r.color}

def _style_verdict(val):
    color = color_map.get(val)
    return f"background-color: {color}; color: white;" if color else ""

def _style_change(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return "color: #1a7e2e;" if val >= 0 else "color: #c62828;"

st.markdown("### All matching picks")
try:
    styler = df.style
    ew = getattr(styler, "map", None) or styler.applymap
    styled = (
        ew(_style_verdict, subset=["Verdict"])
        .pipe(lambda s: (getattr(s, "map", None) or s.applymap)(_style_change, subset=["Day %"]))
        .format({"Score": "{:.1f}",
                 "Day %": lambda v: "—" if v is None or pd.isna(v) else f"{v:+.2f}%"})
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)
except Exception:
    st.dataframe(df, use_container_width=True, hide_index=True)

st.download_button(
    "⬇️ Download picks as CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name=f"top_picks_{exchange}_{horizon}.csv",
    mime="text/csv",
)
st.caption("Open any symbol on the **main analysis page** for the full breakdown, "
           "charts and risk plan. Educational tool — not financial advice.")
