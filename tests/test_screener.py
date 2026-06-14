"""Screener tests using an injected, network-free analyze function."""

from types import SimpleNamespace

import pytest

from stock_analyzer.data import DataError
from stock_analyzer.screener import screen


def _fake_report(score, verdict="Buy"):
    rec = SimpleNamespace(
        verdict=verdict, color="#4caf50", composite_score=score,
        technical_score=score, fundamental_score=score,
        bullish_reasons=[f"Reason for {score}"], bearish_reasons=[],
    )
    meta = {"ticker": "X.NS", "name": "Stock", "price": 100.0,
            "currency": "INR", "change_pct": 1.5}
    return SimpleNamespace(recommendation=rec, meta=meta)


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
