"""Playbook page — the practical stock-analysis guide that drives this tool's logic.

A condensed, in-app reference so the framework behind the scores and the risk
section is always at hand.
"""

import streamlit as st

st.set_page_config(page_title="Playbook — Stock Analyzer", page_icon="📘", layout="wide")

st.title("📘 Practical Market Playbook")
st.caption(
    "Fundamentals decide **what** to buy · technicals decide **when** · risk "
    "management decides **how much**. This framework is wired into the app's scoring."
)

st.warning(
    "**Read this first:** there is no foolproof system. Markets are driven partly by "
    "randomness, human behaviour, and events no one can forecast. Good analysis tilts "
    "probabilities in your favour and manages risk — it does not guarantee outcomes. "
    "Educational reference, **not personalised financial advice**."
)

st.header("Part 1 · Fundamental Analysis — the *what to buy* engine")
st.markdown(
    "- **Top-down context first:** macro (rates, inflation, GDP, credit — rising rates "
    "compress valuations), the sector cycle, and industry structure (Porter's Five Forces).\n"
    "- **The three statements:** income (consistent, *expanding* margins), balance sheet "
    "(current ratio > 1.5, sane debt-to-equity, cash), and cash flow — the hardest to fake. "
    "**Rising earnings with falling cash flow is a red flag.**\n"
    "- **Key ratios — never in isolation:** P/E (vs peers & own history), PEG (P/E vs growth), "
    "P/B (asset-heavy & financials), ROE/ROIC (a moat shows up as ROIC above cost of capital), "
    "Debt/EBITDA (above ~4x gets risky), payout ratio (above ~80% may be unsustainable).\n"
    "- **Qualitative (what ratios miss):** durable **moat** (brand, network effects, switching "
    "costs, patents), **management** capital allocation, and risks (regulation, customer "
    "concentration, obsolescence).\n"
    "- **Valuation:** DCF (run bull/base/bear), relative multiples, and reverse-DCF (what growth "
    "does the price already imply?)."
)
st.info("In this app: P/E, PEG, P/B, ROE, margins, growth, debt-to-equity, **current ratio, "
        "Debt/EBITDA, free cash flow and payout ratio** feed the fundamental score.")

st.header("Part 2 · Technical Analysis — the *when* engine")
st.markdown(
    "- **Trend is the foundation:** higher highs/lows = uptrend; trade with it. Price above a "
    "rising 200-day MA = healthy long-term trend. Golden/death crosses are popular but lagging.\n"
    "- **Structure:** support (buyers) and resistance (sellers) flip roles once broken. "
    "**Volume confirms** — breakouts on high volume are more reliable.\n"
    "- **Use two or three indicators, not ten.** Most are derived from the same price data, so "
    "they're correlated — piling them on creates false confidence. RSI (momentum; extremes can "
    "persist in strong trends), MACD (trend + momentum), volume.\n"
    "- **Chart patterns** are rough probabilities, not certainties."
)
st.info("In this app: SMA/EMA trend & crosses, RSI, MACD, Bollinger Bands, ADX and volume "
        "feed the technical score — and the backtest replays them through history.")

st.header("Part 3 · Combining both — a coherent workflow")
st.markdown(
    "1. **Screen** for fundamentally sound companies.\n"
    "2. **Build a thesis** — why it's mispriced, the catalyst, and what proves you wrong.\n"
    "3. **Time the entry** with technicals (near support in an uptrend, or a confirmed breakout).\n"
    "4. **Define risk first** — position size, stop-loss and the exit trigger, *before* entering.\n"
    "5. **Monitor & review** periodically, not obsessively."
)

st.header("Part 4 · Risk management — matters more than any technique")
st.markdown(
    "- **Position sizing:** never risk more than ~1–2% of capital on a single trade's potential loss.\n"
    "- **Diversify** across stocks, sectors and asset classes.\n"
    "- **Stop-losses / exit rules** decided before you're emotionally invested.\n"
    "- **Risk/reward:** favour setups where reward meaningfully exceeds risk.\n"
    "- **Avoid leverage** until genuinely experienced."
)
st.success("The **🛡️ Risk management** panel on the analysis page applies exactly this: an "
           "ATR-based stop, a target from recent structure, the risk/reward, and a 1–2% "
           "position size from your capital.")

st.header("Part 5 · Honest caveats")
st.markdown(
    "- **No edge is permanent** — published strategies get arbitraged away.\n"
    "- **Backtesting lies if you let it** — overfitting, survivorship bias and ignored costs "
    "flatter results. (The app's backtest excludes costs/slippage/taxes.)\n"
    "- **Behaviour is the biggest risk** — fear, greed, overconfidence and revenge-trading. A "
    "written process and a journal are your best defences.\n"
    "- **Costs and taxes matter**; frequent trading erodes returns.\n"
    "- **Past performance is not future results. Always.**"
)
