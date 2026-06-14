"""News sentiment tests (offline, deterministic)."""

from stock_analyzer.sentiment import analyze_news, score_headline


def test_positive_headline_scores_positive():
    assert score_headline("Company profit surges to record high, beats estimates") > 0.3


def test_negative_headline_scores_negative():
    assert score_headline("Shares crash as firm reports huge loss and fraud probe") < -0.3


def test_neutral_headline_near_zero():
    assert abs(score_headline("Company to hold annual general meeting next week")) < 0.2


def test_negation_flips_polarity():
    # "not" before a positive word should reduce/flip the polarity.
    plain = score_headline("Profit growth strong")
    negated = score_headline("Profit growth not strong")
    assert negated < plain


def test_empty_news_is_neutral():
    res = analyze_news([])
    assert res.score == 50.0
    assert res.headline_count == 0
    assert res.signal.status == "n/a"


def test_aggregate_positive_news_above_50():
    res = analyze_news([
        "Stock surges on record profit",
        "Analysts upgrade with strong buy rating",
    ])
    assert res.score > 50
    assert res.signal.status == "bullish"
    assert res.headline_count == 2


def test_aggregate_negative_news_below_50():
    res = analyze_news([
        "Stock plunges after profit warning",
        "Brokerage downgrades amid weak demand",
    ])
    assert res.score < 50
    assert res.signal.status == "bearish"
