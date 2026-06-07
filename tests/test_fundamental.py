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


def test_missing_metric_is_na_not_zero(strong_fundamentals):
    info = dict(strong_fundamentals)
    info.pop("returnOnEquity")
    res = evaluate(info)
    roe_signal = next(s for s in res.signals if s.name == "ROE")
    assert roe_signal.status == "n/a"
