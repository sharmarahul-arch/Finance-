"""Fundamental scoring tests (offline, synthetic info dicts)."""

from stock_analyzer.fundamental import evaluate


def test_strong_beats_weak(strong_fundamentals, weak_fundamentals):
    strong = evaluate(strong_fundamentals).score
    weak = evaluate(weak_fundamentals).score
    assert strong > 60 > weak
    assert strong > weak


def test_empty_info_is_neutral():
    res = evaluate({})
    assert res.score == 50.0
    # Every signal should be marked unavailable.
    assert all(not s.available for s in res.signals)


def test_debt_equity_percentage_normalized(strong_fundamentals):
    res = evaluate(strong_fundamentals)
    # 30.0 -> 0.30x
    assert abs(res.metrics["Debt/Equity"] - 0.30) < 1e-9


def test_dividend_yield_percentage_normalized():
    # Some yfinance responses give yield as percent (e.g. 2.5 == 2.5%).
    res = evaluate({"dividendYield": 2.5})
    assert abs(res.metrics["Dividend yield"] - 0.025) < 1e-9


def test_company_meta_computes_day_change():
    from stock_analyzer.data import get_company_meta
    meta = get_company_meta("TEST.NS", {
        "longName": "Test Co", "currentPrice": 110.0,
        "regularMarketPreviousClose": 100.0, "currency": "INR",
    })
    assert meta["price"] == 110.0
    assert meta["change"] == 10.0
    assert abs(meta["change_pct"] - 10.0) < 1e-9


def test_company_meta_handles_missing_prev_close():
    from stock_analyzer.data import get_company_meta
    meta = get_company_meta("TEST.NS", {"longName": "Test Co", "currentPrice": 50.0})
    assert meta["price"] == 50.0
    assert meta["change_pct"] is None


def test_guide_signals_present_and_scored():
    info = {
        "currentRatio": 2.0,        # comfortable
        "totalDebt": 100.0, "ebitda": 50.0,   # Debt/EBITDA = 2.0x
        "freeCashflow": 5000.0,     # positive
        "payoutRatio": 0.40,        # sustainable
    }
    res = evaluate(info)
    names = {s.name: s for s in res.signals}
    assert names["Current ratio"].status == "bullish"
    assert names["Debt/EBITDA"].status == "bullish"
    assert names["Free cash flow"].status == "bullish"
    assert names["Payout ratio"].status == "bullish"
    assert abs(res.metrics["Debt/EBITDA"] - 2.0) < 1e-9


def test_guide_signals_flag_weak_fundamentals():
    info = {
        "currentRatio": 0.8,                 # liquidity strain
        "totalDebt": 500.0, "ebitda": 50.0,  # 10x -> high leverage
        "freeCashflow": -2000.0,             # burning cash
        "payoutRatio": 0.95,                 # unsustainable
    }
    res = evaluate(info)
    names = {s.name: s for s in res.signals}
    assert names["Current ratio"].status == "bearish"
    assert names["Debt/EBITDA"].status == "bearish"
    assert names["Free cash flow"].status == "bearish"
    assert names["Payout ratio"].status == "bearish"


def test_payout_ratio_percent_normalized():
    res = evaluate({"payoutRatio": 40.0})   # given as percent
    assert abs(res.metrics["Payout ratio"] - 0.40) < 1e-9


def test_missing_metric_is_na_not_zero(strong_fundamentals):
    info = dict(strong_fundamentals)
    info.pop("returnOnEquity")
    res = evaluate(info)
    roe_signal = next(s for s in res.signals if s.name == "ROE")
    assert roe_signal.status == "n/a"
