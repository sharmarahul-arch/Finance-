# 📈 Stock Analyzer — Technical + Fundamental Analysis (Indian markets)

A Streamlit web app that analyzes Indian stocks (NSE/BSE) using both **technical**
and **fundamental** analysis, then gives a **Buy / Hold / Sell** suggestion tailored
to your **investment horizon** — short term (trading) or long term (investing).

> ⚠️ **Disclaimer:** This tool is for **educational purposes only** and is **not
> financial advice**. Always do your own research before making any investment.

---

## What it does

For any ticker you enter (e.g. `RELIANCE`, `TCS`, `INFY`):

- **Technical analysis** — trend (SMA 20/50/200, golden/death cross), momentum
  (RSI, MACD), volatility (Bollinger Bands), trend strength (ADX) and volume.
- **Fundamental analysis** — valuation (P/E, P/B, PEG), profitability (ROE, margins),
  growth (revenue & earnings), leverage (debt-to-equity) and dividend yield.
- **Horizon-aware verdict** — the same stock can be a "Buy" for a long-term investor
  but a "Hold/Sell" for a short-term trader:
  - **Short term** weights technical signals ~70% (momentum & timing matter most).
  - **Long term** weights fundamentals ~70% (business quality & valuation matter most).
- **Output** — a colour-coded verdict + confidence, a 0–100 composite score gauge,
  the ranked bullish/bearish signals behind it, interactive price/RSI/MACD charts,
  and a fundamentals table.
- **Top Picks (auto-discovery)** — scans a pool of liquid stocks and surfaces the
  highest Buy-rated names automatically, with **market-cap (Large/Mid/Small)** and
  **sector** filters. The top 3 are highlighted as cards; the rest in a ranked table.
- **Multi-stock screener** — paste a watchlist and rank every stock by its
  horizon-weighted score in one go (parallelised), with a sortable table,
  score bar chart and CSV export. Available from the **Screener** page in the
  sidebar navigation.
- **Searchable stock picker** — like Groww/Zerodha, just type a company name or
  symbol and select it (no need to remember exact tickers). Works for both
  **NSE and BSE** — pick the exchange and the picker loads that market's stocks
  (full live lists when online; a bundled list of popular dual-listed names as an
  offline fallback). The screener uses the same picker to build a watchlist.
- **Trading-screen header** — live price with a red/green **day-change %** badge.
- **Favourites / watchlist** — ⭐ save stocks and they persist across sessions;
  quick-load them from the sidebar, or add all your favourites to the screener
  watchlist in one click. The screener table also shows a red/green **day-change %**
  column. Favourites are stored locally by default (a JSON file; path overridable
  with `STOCK_FAV_PATH`) and can optionally use a **durable cloud store** that
  survives redeploys and syncs across devices — see "Durable favourites" below.
- **Risk management (playbook-driven)** — position sizing from the 1–2%
  risk-per-trade rule, an ATR-based stop-loss, a target from recent structure,
  and the resulting risk/reward — so you decide *how much* and *where you're
  wrong* before entering. Plus an in-app **Playbook** page with the full guide.
- **News sentiment** — recent headlines are scored with a finance lexicon and
  folded into the composite (a small, horizon-dependent weight). Headlines are
  shown with their polarity on the single-stock page.
- **Signal backtest** — on the single-stock page, see how a long-only strategy
  that buys on a strong technical score and exits when it weakens would have
  performed on the stock's history, compared against buy-and-hold (return, win
  rate, max drawdown, Sharpe, equity curve). Thresholds are adjustable.

Data comes from **Yahoo Finance** via the free [`yfinance`](https://pypi.org/project/yfinance/)
library — no API key required.

---

## Setup

```bash
# 1. (optional) create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt
```

## Run the app

```bash
streamlit run app.py
```

Then open the URL Streamlit prints (usually http://localhost:8501), type a ticker
in the sidebar, choose **NSE/BSE** and a **horizon**, and click **Analyze**.

## Run the tests

```bash
pytest -q
```

Tests run fully offline using synthetic data (no network calls).

---

## Project structure

```
Finance-/
├── app.py                     # Streamlit UI — single-stock page (home)
├── pages/
│   ├── 1_Screener.py          # Streamlit UI — multi-stock screener page
│   ├── 2_Playbook.py          # Streamlit UI — the analysis guide / framework
│   └── 3_Top_Picks.py         # Streamlit UI — auto top-buy discovery + filters
├── stock_analyzer/            # pure-Python analysis library (UI-free, testable)
│   ├── config.py              # indicator params, thresholds, horizon profiles, verdict bands
│   ├── data.py                # yfinance fetching + ticker normalization
│   ├── indicators.py          # pandas/numpy indicator math (SMA/EMA/RSI/MACD/BB/ADX)
│   ├── technical.py           # technical signals + aggregate score
│   ├── fundamental.py         # fundamental signals + aggregate score
│   ├── recommendation.py      # horizon-weighted verdict + ranked reasons (incl. news)
│   ├── screener.py            # parallel multi-stock ranking
│   ├── sentiment.py           # finance-lexicon news sentiment (offline)
│   ├── risk.py                # position sizing, stop-loss, risk/reward (playbook)
│   ├── backtest.py            # backtest the technical signals vs buy-and-hold
│   ├── engine.py              # orchestration: ticker -> data -> analysis -> verdict
│   └── models.py              # shared Signal dataclass
├── tests/                     # offline unit tests
└── requirements.txt
```

## Using the engine programmatically

```python
from stock_analyzer.engine import analyze_stock

report = analyze_stock("TCS", exchange="NSE", horizon="long_term")
print(report.recommendation.verdict, report.recommendation.composite_score)
for reason in report.recommendation.bullish_reasons:
    print("+", reason)
```

Screen and rank a watchlist:

```python
from stock_analyzer.screener import screen

summary = screen(["RELIANCE", "TCS", "INFY"], exchange="NSE", horizon="long_term")
for r in summary.ranked:
    print(f"{r.symbol:12} {r.verdict:11} {r.composite_score}")
```

Backtest the signals on a price history:

```python
from stock_analyzer.engine import analyze_stock

report = analyze_stock("TCS", horizon="short_term", include_backtest=True)
bt = report.backtest
print(f"Strategy: {bt.total_return*100:.1f}%  vs  Buy&Hold: {bt.buy_hold_return*100:.1f}%")
print(f"Trades: {bt.num_trades}  Win rate: {bt.win_rate}  Max DD: {bt.max_drawdown*100:.1f}%")
```

## Durable favourites (optional cloud store)

By default favourites are saved to a local JSON file, which resets when a Streamlit
Cloud app redeploys. To make them durable and shared across devices, point the app
at a free [Supabase](https://supabase.com) project:

1. Create a Supabase project, then in the SQL editor create the table:

   ```sql
   create table favourites (
     id bigint generated always as identity primary key,
     user_id text not null default 'default',
     symbol text not null,
     exchange text not null,
     name text,
     unique (user_id, symbol, exchange)
   );
   ```

2. In Streamlit Cloud, open **Manage app → Settings → Secrets** and add:

   ```toml
   SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
   SUPABASE_KEY = "YOUR-ANON-OR-SERVICE-KEY"
   STOCK_USER   = "default"   # optional: namespace per user
   ```

   (Locally, set the same values as environment variables instead.)

The sidebar shows whether favourites are in **local** or **☁ cloud** mode. If the
cloud store is ever unreachable, the app automatically falls back to local storage.

## Tuning

All thresholds, indicator periods, scoring weights and verdict bands live in
`stock_analyzer/config.py` — adjust them there to match your own strategy.

## Notes & limitations

- yfinance data can be delayed or incomplete; missing fundamentals are shown as
  "N/A" and excluded from the score rather than penalising the stock.
- Signals are heuristic and equally weighted within each category; this is a
  decision-support tool, not a predictive model.
