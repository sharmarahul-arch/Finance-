"""Streamlit dashboard for stock technical + fundamental analysis (Indian markets).

Run with:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from stock_analyzer import data as data_mod
from stock_analyzer import favourites as favourites_mod
from stock_analyzer import universe as universe_mod
from stock_analyzer.backtest import run_backtest
from stock_analyzer.config import HORIZONS
from stock_analyzer.data import DataError
from stock_analyzer.engine import analyze_stock
from stock_analyzer.risk import compute_risk_plan

st.set_page_config(page_title="Stock Analyzer — India", page_icon="📈", layout="wide")


def _configure_favourites_backend():
    """Bridge optional Supabase secrets to the favourites store (cloud mode)."""
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
        if url and key:
            favourites_mod.configure(
                supabase_url=url, supabase_key=key,
                user=st.secrets.get("STOCK_USER", "default"),
            )
    except Exception:
        pass  # no secrets file / not configured -> stay in local mode


_configure_favourites_backend()


# --------------------------------------------------------------------------- #
# Cached data wrappers (Streamlit-side caching; the library itself stays clean)
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=900, show_spinner=False)
def _cached_analyze(symbol: str, exchange: str, horizon: str):
    return analyze_stock(symbol, exchange=exchange, horizon=horizon, include_news=True)


@st.cache_data(ttl=86400, show_spinner="Loading stock list…")
def _load_universe(exchange: str):
    return universe_mod.load_universe(exchange)


def _fmt_money(value, currency="INR"):
    if value is None:
        return "—"
    symbol = "₹" if currency == "INR" else ""
    try:
        return f"{symbol}{value:,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _buy_call(verdict: str):
    """Map the verdict to a plain-language 'should I buy?' answer + colour."""
    v = (verdict or "").lower()
    if "buy" in v:
        return "✅", "YES", "looks like a buy", "#1a7e2e"
    if "sell" in v:
        return "❌", "NO", "not a buy right now — consider avoiding/selling", "#c62828"
    return "🟡", "WAIT", "no clear edge yet — better to hold/watch", "#f0ad4e"


def _fmt_metric(name, value):
    if value is None:
        return "N/A"
    if name in {"ROE", "Net margin", "Revenue growth", "Earnings growth",
                "Dividend yield", "Payout ratio"}:
        return f"{value * 100:.1f}%"
    if name in {"Market cap", "Free cash flow"}:
        return f"₹{value/1e7:,.0f} Cr"  # 1 crore = 1e7
    if name == "Debt/EBITDA":
        return f"{value:.1f}x"
    return f"{value:,.2f}"


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
def price_chart(df: pd.DataFrame, name: str):
    """Candlestick + moving averages, with RSI and MACD sub-panels."""
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03,
        subplot_titles=(f"{name} — Price & Moving Averages", "RSI", "MACD"),
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="Price",
        ),
        row=1, col=1,
    )
    for col, color in [("SMA20", "#1f77b4"), ("SMA50", "#ff7f0e"), ("SMA200", "#9467bd")]:
        if col in df and df[col].notna().any():
            fig.add_trace(
                go.Scatter(x=df.index, y=df[col], name=col, line=dict(width=1, color=color)),
                row=1, col=1,
            )

    if "RSI" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="#2ca02c")),
                      row=2, col=1)
        fig.add_hline(y=70, line=dict(color="red", dash="dot"), row=2, col=1)
        fig.add_hline(y=30, line=dict(color="green", dash="dot"), row=2, col=1)

    if "MACD" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(color="#1f77b4")),
                      row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD_SIGNAL"], name="Signal",
                                 line=dict(color="#ff7f0e")), row=3, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df["MACD_HIST"], name="Histogram",
                             marker_color="#888"), row=3, col=1)

    fig.update_layout(
        height=720, xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def gauge(score: float, color: str):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": " / 100"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 25], "color": "#fadbd8"},
                {"range": [25, 40], "color": "#fdebd0"},
                {"range": [40, 60], "color": "#fcf3cf"},
                {"range": [60, 75], "color": "#d5f5e3"},
                {"range": [75, 100], "color": "#abebc6"},
            ],
        },
    ))
    fig.update_layout(height=240, margin=dict(l=20, r=20, t=20, b=10))
    return fig


# --------------------------------------------------------------------------- #
# Sidebar — inputs
# --------------------------------------------------------------------------- #
st.sidebar.title("📈 Stock Analyzer")
st.sidebar.caption("Technical + fundamental analysis for Indian stocks")


def _select_stock(sym: str, exch: str):
    """Callback used by the favourites list to jump to a saved stock."""
    st.session_state["exchange"] = exch
    st.session_state["symbol"] = sym


exchange = st.sidebar.selectbox("Exchange", ["NSE", "BSE"], index=0, key="exchange")

universe = _load_universe(exchange)
options = [r["symbol"] for r in universe]
labels = {r["symbol"]: f"{r['name']} ({r['symbol']})" for r in universe}
default_idx = options.index("RELIANCE") if "RELIANCE" in options else 0

# Keep the persisted picker value valid when the exchange changes.
if st.session_state.get("symbol") not in options:
    st.session_state.pop("symbol", None)

symbol = st.sidebar.selectbox(
    f"🔍 Search a stock ({exchange})",
    options=options,
    index=default_idx,
    format_func=lambda s: labels.get(s, s),
    help="Type a company name or symbol, e.g. Reliance, Infosys, HDFC…",
    key="symbol",
)
horizon_label = st.sidebar.radio(
    "Investment horizon",
    options=[HORIZONS["short_term"].label, HORIZONS["long_term"].label],
)
horizon = "short_term" if horizon_label == HORIZONS["short_term"].label else "long_term"
st.sidebar.caption(HORIZONS[horizon].description)

if st.sidebar.button("🔄 Refresh data", use_container_width=True,
                     help="Clear the 15-min cache and re-fetch the latest from Yahoo."):
    st.cache_data.clear()
    st.rerun()

# --- Favourites quick-load -------------------------------------------------- #
st.sidebar.markdown("---")
_mode = favourites_mod.storage_mode()
st.sidebar.markdown(f"### ⭐ Favourites &nbsp; <span style='font-size:0.7rem;opacity:0.6'>"
                    f"({'☁ cloud' if _mode == 'cloud' else 'local'})</span>",
                    unsafe_allow_html=True)

if _mode == "cloud":
    if st.sidebar.button("🔌 Test cloud connection", use_container_width=True):
        st.session_state["_cloud_status"] = favourites_mod.check_connection()
    _status = st.session_state.get("_cloud_status")
    if _status:
        (st.sidebar.success if _status["ok"] else st.sidebar.error)(_status["message"])

favs = favourites_mod.load_favourites(exchange)
if not favs:
    st.sidebar.caption(f"No saved {exchange} stocks yet. Use the ⭐ button on a stock.")
else:
    for f in favs:
        st.sidebar.button(
            f"⭐ {labels.get(f['symbol'], f.get('name') or f['symbol'])}",
            key=f"fav_{exchange}_{f['symbol']}",
            on_click=_select_stock,
            args=(f["symbol"], exchange),
            use_container_width=True,
        )

st.sidebar.markdown("---")
st.sidebar.warning(
    "**Disclaimer:** This tool is for educational purposes only and is **not "
    "financial advice**. Do your own research before investing."
)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
st.title("Stock Analysis & Investment Suggestion")

if not symbol:
    st.info("🔍 Search and select a stock from the sidebar to begin.")
    st.stop()

try:
    with st.spinner(f"Analyzing {symbol} ({exchange})…"):
        report = _cached_analyze(symbol, exchange, horizon)
except DataError as exc:
    st.error(str(exc))
    st.stop()
except Exception as exc:  # noqa: BLE001 -- surface anything else cleanly
    st.error(f"Unexpected error: {exc}")
    st.stop()

meta = report.meta
rec = report.recommendation

# --- Header ----------------------------------------------------------------- #
title_col, star_col = st.columns([5, 1])
title_col.subheader(f"{meta['name']}  ·  `{meta['ticker']}`")
saved = favourites_mod.is_favourite(symbol, exchange)
if star_col.button("★ Saved" if saved else "☆ Save", use_container_width=True,
                   help="Add/remove from your favourites"):
    favourites_mod.toggle_favourite(symbol, exchange, meta["name"])
    st.rerun()

# Live price with a red/green day-change delta (st.metric colours it automatically).
day_delta = None
if meta.get("change_pct") is not None:
    day_delta = f"{meta['change']:+,.2f} ({meta['change_pct']:+.2f}%)"

c1, c2, c3 = st.columns(3)
c1.metric("Live price", _fmt_money(meta["price"], meta["currency"]), delta=day_delta)
c2.metric("Sector", meta["sector"])
c3.metric("Horizon", HORIZONS[horizon].label)
st.caption(
    "ℹ️ Prices via Yahoo Finance are usually **delayed ~15 minutes** and can differ "
    "slightly from your broker's real-time feed. Use 🔄 Refresh for the latest."
)

# --- Plain-language "Should I buy?" answer (automatic, no input needed) ------ #
_emoji, _answer, _sub, _bcolor = _buy_call(rec.verdict)
st.markdown(
    f"<div style='padding:1.1rem 1.4rem;border-radius:14px;background:{_bcolor};"
    f"color:white;margin:0.4rem 0'>"
    f"<div style='font-size:1.0rem;opacity:0.92'>Should you buy {meta['name']}? "
    f"({HORIZONS[horizon].label})</div>"
    f"<div style='font-size:2.2rem;font-weight:800'>{_emoji} {_answer} &nbsp;"
    f"<span style='font-size:1.0rem;font-weight:500;opacity:0.95'>— {_sub}</span></div>"
    f"<div style='font-size:0.9rem;opacity:0.92'>Verdict: {rec.verdict} · "
    f"Score {rec.composite_score}/100 · Confidence {rec.confidence:.0f}%</div>"
    f"</div>",
    unsafe_allow_html=True,
)

# --- Verdict + gauge -------------------------------------------------------- #
v1, v2 = st.columns([1, 1])
with v1:
    st.markdown(
        f"<div style='padding:1.2rem;border-radius:12px;background:{rec.color};"
        f"color:white;text-align:center'>"
        f"<div style='font-size:0.9rem;opacity:0.9'>VERDICT ({HORIZONS[horizon].label})</div>"
        f"<div style='font-size:2.4rem;font-weight:700'>{rec.verdict}</div>"
        f"<div style='font-size:0.95rem'>Confidence: {rec.confidence:.0f}%</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    caption = (
        f"Composite {rec.composite_score}/100  ·  "
        f"Technical {rec.technical_score}  ·  Fundamental {rec.fundamental_score}"
    )
    if rec.news_score is not None:
        caption += f"  ·  News {rec.news_score}"
    st.caption(caption)
with v2:
    st.plotly_chart(gauge(rec.composite_score, rec.color), use_container_width=True)

# --- Reasoning -------------------------------------------------------------- #
r1, r2 = st.columns(2)
with r1:
    st.markdown("#### ✅ Bullish signals")
    if rec.bullish_reasons:
        for reason in rec.bullish_reasons:
            st.markdown(f"- {reason}")
    else:
        st.caption("No notable bullish signals.")
with r2:
    st.markdown("#### ⚠️ Bearish signals")
    if rec.bearish_reasons:
        for reason in rec.bearish_reasons:
            st.markdown(f"- {reason}")
    else:
        st.caption("No notable bearish signals.")

# --- Charts ----------------------------------------------------------------- #
st.markdown("### Price & indicators")
st.plotly_chart(price_chart(report.technical.enriched, meta["name"]), use_container_width=True)

# --- Fundamentals table ----------------------------------------------------- #
st.markdown("### Fundamental metrics")
metrics = report.fundamental.metrics
rows = [{"Metric": k, "Value": _fmt_metric(k, v)} for k, v in metrics.items()]
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# --- News sentiment --------------------------------------------------------- #
st.markdown("### 📰 News sentiment")
news = report.news
if news is None or news.headline_count == 0:
    st.caption("No recent headlines found for this stock.")
else:
    st.caption(
        f"{news.headline_count} recent headlines · sentiment score "
        f"{news.score}/100 ({news.signal.status})."
    )
    for item in news.per_headline:
        pol = item["polarity"]
        emoji = "🟢" if pol > 0.15 else ("🔴" if pol < -0.15 else "⚪")
        st.markdown(f"{emoji} {item['headline']}  &nbsp; `({pol:+.2f})`", unsafe_allow_html=True)

# --- Strategy backtest ------------------------------------------------------ #
st.markdown("### 🧪 Signal backtest")
st.caption(
    "How a long-only strategy that buys on a strong technical score and exits when "
    "it weakens would have performed on this price history — vs simply buying & holding."
)
buy_th, exit_th = 60, 45   # sensible defaults — no input required
with st.expander("⚙️ Adjust backtest thresholds (optional)"):
    bc1, bc2 = st.columns(2)
    buy_th = bc1.slider("Buy when score ≥", 50, 90, 60, step=5)
    exit_th = bc2.slider("Exit when score ≤", 10, 50, 45, step=5)

bt = run_backtest(report.price_df, buy_threshold=buy_th, exit_threshold=exit_th)
if not bt.ok:
    st.info(bt.message)
else:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Strategy return", f"{bt.total_return*100:.1f}%")
    m2.metric("Buy & hold return", f"{bt.buy_hold_return*100:.1f}%",
              delta=f"{(bt.total_return-bt.buy_hold_return)*100:.1f}% vs B&H")
    m3.metric("Win rate", f"{bt.win_rate*100:.0f}%" if bt.win_rate is not None else "—")
    m4.metric("Max drawdown", f"{bt.max_drawdown*100:.1f}%")
    n1, n2, n3 = st.columns(3)
    n1.metric("Trades", bt.num_trades)
    n2.metric("Time in market", f"{bt.exposure*100:.0f}%")
    n3.metric("Sharpe", f"{bt.sharpe:.2f}" if bt.sharpe is not None else "—")

    eq = go.Figure()
    eq.add_trace(go.Scatter(x=bt.equity_curve.index, y=bt.equity_curve,
                            name="Strategy", line=dict(color="#1a7e2e")))
    eq.add_trace(go.Scatter(x=bt.buy_hold_curve.index, y=bt.buy_hold_curve,
                            name="Buy & hold", line=dict(color="#888", dash="dot")))
    eq.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                     yaxis_title="Growth of ₹1",
                     legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(eq, use_container_width=True)
    st.caption(
        "Backtests are hypothetical, exclude costs/slippage/taxes, and past "
        "performance does not guarantee future results."
    )

# --- Risk management (from the playbook) ------------------------------------ #
st.markdown("### 🛡️ Risk management")
st.caption(
    "Auto-computed stop-loss, target and risk/reward using sensible defaults "
    "(₹1,00,000 capital · 1% risk per trade · 2× ATR stop). No input needed — "
    "expand below only if you want to tailor it."
)
# Sensible defaults so the plan is fully automatic; the inputs are optional.
account_size, risk_pct, atr_mult = 100000, 1.0, 2.0
with st.expander("⚙️ Adjust position-sizing assumptions (optional)"):
    rc1, rc2, rc3 = st.columns(3)
    account_size = rc1.number_input("Your capital (₹)", min_value=0, value=100000, step=10000)
    risk_pct = rc2.slider("Risk per trade (%)", 0.5, 5.0, 1.0, step=0.5,
                          help="Playbook suggests 1–2%.")
    atr_mult = rc3.slider("Stop distance (× ATR)", 1.0, 4.0, 2.0, step=0.5)

plan = compute_risk_plan(report.price_df, account_size, risk_pct=risk_pct, atr_mult=atr_mult)
if not plan.ok:
    st.info(plan.message)
else:
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Entry (last close)", _fmt_money(plan.entry))
    p2.metric("Stop-loss", _fmt_money(plan.stop_loss), delta=f"-{plan.stop_pct:.1f}%")
    p3.metric("Target", _fmt_money(plan.target))
    rr_txt = f"{plan.risk_reward:.2f} : 1" if plan.risk_reward is not None else "—"
    p4.metric("Risk / reward", rr_txt)
    q1, q2, q3 = st.columns(3)
    q1.metric("Suggested size", f"{plan.shares:,} shares")
    q2.metric("Position value", _fmt_money(plan.position_value))
    q3.metric("Capital at risk", _fmt_money(plan.capital_at_risk))
    if plan.capped_by_capital:
        st.caption("⚠️ Position limited by available capital (the full risk-based size "
                   "would exceed your stated capital).")
    if plan.risk_reward is not None and plan.risk_reward < 1.5:
        st.warning("Risk/reward is below ~1.5 — the playbook favours setups where the "
                   "potential reward meaningfully exceeds the risk.")

# --- Workflow checklist (the guide's coherent workflow) --------------------- #
with st.expander("📋 The workflow checklist (what → when → how much)"):
    st.markdown(
        "1. **Screen** — fundamentally sound: good returns, sane valuation, strong "
        "balance sheet, a durable moat.\n"
        "2. **Build a thesis** — *why* is it mispriced, what's the catalyst, and what "
        "would prove you wrong?\n"
        "3. **Time the entry** — technicals: buy near support in an uptrend, or a "
        "confirmed breakout (volume confirms).\n"
        "4. **Define risk first** — position size, stop-loss and the thesis-breaking "
        "news that forces an exit — *before* entering.\n"
        "5. **Monitor & review** — periodically, not obsessively. Keep a journal.\n\n"
        "> **Fundamentals decide _what_, technicals decide _when_, risk management "
        "decides _how much_** — the part that keeps an account solvent. "
        "See the **Playbook** page for the full guide."
    )

st.markdown("---")
st.caption(
    "Educational tool — **not financial advice**. No system is foolproof; markets are "
    "partly random, and behaviour (fear, greed, revenge-trading) destroys more accounts "
    "than bad analysis. Data via Yahoo Finance (yfinance), which may be delayed or incomplete."
)
