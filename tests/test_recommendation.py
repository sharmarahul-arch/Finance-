"""Recommendation engine + horizon-weighting tests."""

import pytest

from stock_analyzer.fundamental import evaluate as eval_fundamental
from stock_analyzer.recommendation import recommend
from stock_analyzer.technical import evaluate as eval_technical


def test_horizon_weighting_shifts_score(uptrend_df, weak_fundamentals):
    """Strong technicals + weak fundamentals: short term should score higher
    than long term, because short term weights technicals more heavily."""
    tech = eval_technical(uptrend_df)
    fund = eval_fundamental(weak_fundamentals)

    short = recommend(tech, fund, horizon="short_term")
    long = recommend(tech, fund, horizon="long_term")

    assert short.composite_score > long.composite_score


def test_long_term_favours_fundamentals(downtrend_df, strong_fundamentals):
    """Weak technicals + strong fundamentals: long term should score higher."""
    tech = eval_technical(downtrend_df)
    fund = eval_fundamental(strong_fundamentals)

    short = recommend(tech, fund, horizon="short_term")
    long = recommend(tech, fund, horizon="long_term")

    assert long.composite_score > short.composite_score


def test_strong_all_round_is_buy(uptrend_df, strong_fundamentals):
    tech = eval_technical(uptrend_df)
    fund = eval_fundamental(strong_fundamentals)
    rec = recommend(tech, fund, horizon="long_term")
    assert rec.verdict in {"Buy", "Strong Buy"}
    assert rec.bullish_reasons  # has at least one reason


def test_weak_all_round_is_sell(downtrend_df, weak_fundamentals):
    tech = eval_technical(downtrend_df)
    fund = eval_fundamental(weak_fundamentals)
    rec = recommend(tech, fund, horizon="long_term")
    assert rec.verdict in {"Sell", "Strong Sell"}
    assert rec.bearish_reasons


def test_invalid_horizon_raises(uptrend_df, strong_fundamentals):
    tech = eval_technical(uptrend_df)
    fund = eval_fundamental(strong_fundamentals)
    with pytest.raises(ValueError):
        recommend(tech, fund, horizon="medium_term")


def test_confidence_in_range(uptrend_df, strong_fundamentals):
    tech = eval_technical(uptrend_df)
    fund = eval_fundamental(strong_fundamentals)
    rec = recommend(tech, fund, horizon="long_term")
    assert 0 <= rec.confidence <= 100
