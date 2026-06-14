"""Universe loader tests (offline — exercises the bundled fallback)."""

from stock_analyzer import universe


def test_bundled_list_loads():
    rows = universe._load_bundled()
    assert len(rows) > 50
    assert all("symbol" in r and "name" in r for r in rows)
    symbols = {r["symbol"] for r in rows}
    assert "RELIANCE" in symbols and "TCS" in symbols


def test_load_universe_offline_falls_back(monkeypatch):
    # Force the live download to fail -> must fall back to the bundled list.
    universe.load_universe.cache_clear()
    monkeypatch.setattr(universe, "_download_nse_csv", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    rows = universe.load_universe(prefer_live=True)
    assert len(rows) > 50
    universe.load_universe.cache_clear()


def test_search_matches_name_and_symbol(monkeypatch):
    universe.load_universe.cache_clear()
    monkeypatch.setattr(universe, "_download_nse_csv", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    assert any(r["symbol"] == "INFY" for r in universe.search("infosys"))
    assert any(r["symbol"] == "TCS" for r in universe.search("TCS"))
    assert universe.search("zzzzznotastock") == []
    universe.load_universe.cache_clear()


def test_bse_offline_falls_back_to_bundled(monkeypatch):
    universe.load_universe.cache_clear()
    monkeypatch.setattr(universe, "_download_bse",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    rows = universe.load_universe(market="BSE", prefer_live=True)
    assert len(rows) > 50  # bundled dual-listed names work on BSE (.BO) too
    universe.load_universe.cache_clear()


def test_parse_nse_csv_handles_spaced_headers():
    csv_text = (
        "SYMBOL, NAME OF COMPANY, SERIES, DATE OF LISTING\n"
        "ACME,Acme Ltd,EQ,01-JAN-2000\n"
        "DEBT1,Debt Co,N1,01-JAN-2000\n"      # non-equity series filtered out
    )
    rows = universe._parse_nse_csv(csv_text)
    syms = {r["symbol"] for r in rows}
    assert "ACME" in syms
    assert "DEBT1" not in syms
