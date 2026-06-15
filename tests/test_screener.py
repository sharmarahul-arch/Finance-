"""Screener tests using an injected, network-free analyze function."""

from types import SimpleNamespace

import pytest

from stock_analyzer.data import DataError
from stock_analyzer.screener import screen


def _fake_report(score, verdict="Buy", sector="Tech", market_cap=3e11):
    rec = SimpleNamespace(
        verdict=verdict, color="#4caf50", composite_score=score,
        technical_score=score, fundamental_score=score,
        bullish_reasons=[f"Reason for {score}"], bearish_reasons=[],
    )
    meta = {"ticker": "X.NS", "name": "Stock", "price": 100.0,
            "currency": "INR", "change_pct": 1.5, "sector": sector}
    fundamental = SimpleNamespace(metrics={"Market cap": market_cap})
    return SimpleNamespace(recommendation=rec, meta=meta, fundamental=fundamental)


def make_fake_analyze(scores):
    """Return an analyze_fn that maps each symbol to a preset score."""
    def _fn(symbol, exchange="NSE", horizon="long_term"):
        key = symbol.strip().upper()
        if key not in scores:
            raise DataError(f"No data for {symbol}")
        return _fake_report(scores[key])
    return _fn


def test_ranking_is_descending_by_score():
    fn = make_fake_analyze({"AAA": 80, "BBB": 40, "CCC": 60})
    summary = screen(["AAA", "BBB", "CCC"], analyze_fn=fn)
    ordered = [r.symbol for r in summary.ranked]
    assert ordered == ["AAA", "CCC", "BBB"]


def test_failures_are_captured_not_raised():
    fn = make_fake_analyze({"GOOD": 70})
    summary = screen(["GOOD", "BADSYM"], analyze_fn=fn)
    assert len(summary.succeeded) == 1
    assert len(summary.failed) == 1
    assert summary.failed[0].symbol == "BADSYM"
    assert "No data" in summary.failed[0].error


def test_failures_rank_last():
    fn = make_fake_analyze({"GOOD": 30})
    summary = screen(["BADSYM", "GOOD"], analyze_fn=fn)
    # Even a low-scoring success outranks a failure.
    assert summary.ranked[0].symbol == "GOOD"
    assert summary.ranked[-1].symbol == "BADSYM"


def test_duplicates_and_blanks_removed():
    fn = make_fake_analyze({"AAA": 50})
    summary = screen(["AAA", "aaa", "  ", "AAA"], analyze_fn=fn)
    assert len(summary.results) == 1


def test_empty_input_returns_empty_summary():
    summary = screen([], analyze_fn=make_fake_analyze({}))
    assert summary.results == []
    assert summary.ranked == []


def test_invalid_horizon_raises():
    with pytest.raises(ValueError):
        screen(["AAA"], horizon="medium", analyze_fn=make_fake_analyze({"AAA": 50}))


def test_top_reason_populated():
    fn = make_fake_analyze({"AAA": 80})
    summary = screen(["AAA"], analyze_fn=fn)
    assert summary.succeeded[0].top_reason == "Reason for 80"


def test_change_pct_propagated():
    fn = make_fake_analyze({"AAA": 80})
    summary = screen(["AAA"], analyze_fn=fn)
    assert summary.succeeded[0].change_pct == 1.5


def test_sector_and_cap_propagated():
    fn = make_fake_analyze({"AAA": 80})
    summary = screen(["AAA"], analyze_fn=fn)
    r = summary.succeeded[0]
    assert r.sector == "Tech"
    assert r.market_cap == 3e11
    assert r.cap_category == "Large"   # 3e11 = ₹30,000 cr


def test_progress_callback_reports_completion():
    fn = make_fake_analyze({"AAA": 70, "BBB": 60, "CCC": 50})
    calls = []
    summary = screen(["AAA", "BBB", "CCC"], analyze_fn=fn,
                     progress_callback=lambda done, total: calls.append((done, total)))
    assert len(summary.succeeded) == 3
    assert calls[-1] == (3, 3)               # final call reports all done
    assert [c[0] for c in calls] == [1, 2, 3]  # monotonically increasing
    assert all(c[1] == 3 for c in calls)       # total constant


def test_cap_bucket_thresholds():
    from stock_analyzer.screener import cap_bucket
    assert cap_bucket(3e11) == "Large"      # ₹30,000 cr
    assert cap_bucket(1e11) == "Mid"        # ₹10,000 cr
    assert cap_bucket(1e10) == "Small"      # ₹1,000 cr
    assert cap_bucket(None) is None
    assert cap_bucket(0) is None
