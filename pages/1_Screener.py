"""Multi-stock screener page: analyse a watchlist and rank by horizon-weighted score.

Streamlit automatically adds files in ``pages/`` to the sidebar navigation; the
main single-stock app (``app.py``) remains the home page.
"""

from __future__ import annotations

import re

import pandas as pd
import plotly.express as px
import streamlit as st

from stock_analyzer.config import HORIZONS
from stock_analyzer.screener import screen

st.set_page_config(page_title="Screener — Stock Analyzer", page_icon="📊", layout="wide")

DEFAULT_WATCHLIST = (
    "RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, ITC, LT, HINDUNILVR, BHARTIARTL"
)
MAX_TICKERS = 30


@st.cache_data(ttl=900, show_spinner=False)
def _cached_screen(symbols: tuple, exchange: str, horizon: str):
    # Tuple input keeps the cache key hashable/stable.
    return screen(list(symbols), exchange=exchange, horizon=horizon)


def _parse_symbols(raw: str):
    """Split on commas / whitespace / newlines into a clean symbol list."""
    parts = re.split(r"[\s,]+", raw.strip())
    return [p for p in parts if p]


def _fmt_money(value, currency="INR"):
    if value is None:
        return "—"
    prefix = "₹" if currency == "INR" else ""
    try:
        return f"{prefix}{value:,.2f}"
    except (TypeError, ValueError):
        return str(value)


# --------------------------------------------------------------------------- #
# Sidebar inputs
# --------------------------------------------------------------------------- #
st.sidebar.title("📊 Screener")
st.sidebar.caption("Rank a watchlist by Buy/Sell score")

raw_symbols = st.sidebar.text_area(
    "Tickers",
    value=DEFAULT_WATCHLIST,
    height=120,
    help="Separate with commas, spaces or new lines. Up to "
         f"{MAX_TICKERS} symbols.",
)
exchange = st.sidebar.selectbox("Exchange", ["NSE", "BSE"], index=0)
horizon_label = st.sidebar.radio(
    "Investment horizon",
    options=[HORIZONS["short_term"].label, HORIZONS["long_term"].label],
)
horizon = "short_term" if horizon_label == HORIZONS["short_term"].label else "long_term"
st.sidebar.caption(HORIZONS[horizon].description)
run = st.sidebar.button("Run screener", type="primary", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.warning(
    "**Disclaimer:** Educational tool, **not financial advice**. "
    "Do your own research before investing."
)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
st.title("Multi-Stock Screener")
st.caption(
    "Analyses each stock with the same technical + fundamental engine as the "
    "single-stock page, then ranks them by the horizon-weighted composite score."
)

if not run:
    st.info("Enter a watchlist in the sidebar, choose a horizon, and click **Run screener**.")
    st.stop()

symbols = _parse_symbols(raw_symbols)
if not symbols:
    st.error("Please enter at least one ticker.")
    st.stop()
if len(symbols) > MAX_TICKERS:
    st.warning(f"Limiting to the first {MAX_TICKERS} tickers (you entered {len(symbols)}).")
    symbols = symbols[:MAX_TICKERS]

with st.spinner(f"Screening {len(symbols)} stocks ({exchange}, {HORIZONS[horizon].label})…"):
    summary = _cached_screen(tuple(symbols), exchange, horizon)

ranked = summary.ranked
ok = [r for r in ranked if r.ok]
failed = summary.failed

# --- Summary metrics -------------------------------------------------------- #
c1, c2, c3 = st.columns(3)
c1.metric("Analysed", f"{len(ok)}/{len(symbols)}")
buys = sum(1 for r in ok if r.verdict in {"Buy", "Strong Buy"})
sells = sum(1 for r in ok if r.verdict in {"Sell", "Strong Sell"})
c2.metric("Buy / Strong Buy", buys)
c3.metric("Sell / Strong Sell", sells)

if not ok:
    st.error("No stocks could be analysed. Check the symbols / exchange and try again.")
    if failed:
        st.subheader("Failures")
        st.dataframe(
            pd.DataFrame([{"Symbol": r.symbol, "Error": r.error} for r in failed]),
            use_container_width=True, hide_index=True,
        )
    st.stop()

# --- Ranked table ----------------------------------------------------------- #
rows = []
for i, r in enumerate(ok, start=1):
    rows.append({
        "Rank": i,
        "Symbol": r.symbol,
        "Name": r.name,
        "Verdict": r.verdict,
        "Score": r.composite_score,
        "Technical": r.technical_score,
        "Fundamental": r.fundamental_score,
        "Price": _fmt_money(r.price, r.currency),
        "Top signal": r.top_reason or "—",
    })
df = pd.DataFrame(rows)

# Colour the Verdict cell by its band colour.
color_map = {r.verdict: r.color for r in ok if r.verdict and r.color}

def _style_verdict(val):
    color = color_map.get(val)
    return f"background-color: {color}; color: white;" if color else ""

styled = df.style.applymap(_style_verdict, subset=["Verdict"]).format(
    {"Score": "{:.1f}", "Technical": "{:.1f}", "Fundamental": "{:.1f}"}
)

st.markdown("### Ranking")
st.dataframe(styled, use_container_width=True, hide_index=True)

st.download_button(
    "⬇️ Download as CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name=f"screener_{exchange}_{horizon}.csv",
    mime="text/csv",
)

# --- Score chart ------------------------------------------------------------ #
st.markdown("### Composite scores")
chart_df = pd.DataFrame({
    "Symbol": [r.symbol for r in ok],
    "Score": [r.composite_score for r in ok],
    "Verdict": [r.verdict for r in ok],
})
fig = px.bar(
    chart_df.sort_values("Score"),
    x="Score", y="Symbol", orientation="h", color="Verdict",
    color_discrete_map=color_map, range_x=[0, 100],
)
fig.add_vline(x=50, line=dict(color="grey", dash="dot"))
fig.update_layout(height=max(300, 28 * len(ok)), margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

# --- Failures --------------------------------------------------------------- #
if failed:
    with st.expander(f"⚠️ {len(failed)} ticker(s) could not be analysed"):
        st.dataframe(
            pd.DataFrame([{"Symbol": r.symbol, "Error": r.error} for r in failed]),
            use_container_width=True, hide_index=True,
        )

st.markdown("---")
st.caption("Educational tool — not financial advice. Data via Yahoo Finance (yfinance).")
