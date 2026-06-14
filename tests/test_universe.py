"""Universe loader tests (offline — exercises the bundled fallback)."""

import pytest

from stock_analyzer import universe


def _raise(*a, **k):
    raise RuntimeError("network blocked in tests")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Block real HTTP and clear the cache so tests never hit the wire.

    Patching ``requests.get`` blocks every live source uniformly; tests that
    exercise a specific parser supply their own fake ``requests.get``.
    """
    universe.load_universe.cache_clear()
    import requests
    monkeypatch.setattr(requests, "get", _raise)
    yield
    universe.load_universe.cache_clear()


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


def test_kite_parser_filters_nse_equities(monkeypatch):
    sample = (
        "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,"
        "tick_size,lot_size,instrument_type,segment,exchange\n"
        "1,1,INFY,INFOSYS,0,,0,0.05,1,EQ,NSE,NSE\n"
        "2,2,RELIANCE,RELIANCE INDUSTRIES,0,,0,0.05,1,EQ,NSE,NSE\n"
        "3,3,NIFTY24JUNFUT,NIFTY,0,2024-06-27,0,0.05,50,FUT,NFO-FUT,NFO\n"  # not equity
        "4,4,SOMEBSE,Some BSE Co,0,,0,0.05,1,EQ,BSE,BSE\n"                  # wrong exchange
    )
    import requests
    class _Resp:
        text = sample
        def raise_for_status(self): pass
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp())
    rows = universe._download_kite("NSE")
    syms = {r["symbol"] for r in rows}
    assert syms == {"INFY", "RELIANCE"}
    assert next(r for r in rows if r["symbol"] == "INFY")["name"] == "INFOSYS"


def test_load_universe_uses_first_good_source(monkeypatch):
    universe.load_universe.cache_clear()
    big = [{"symbol": f"S{i}", "name": f"Co {i}"} for i in range(100)]
    monkeypatch.setattr(universe, "_download_nse_csv",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nse blocked")))
    monkeypatch.setattr(universe, "_download_kite", lambda *a, **k: big)
    monkeypatch.setattr(universe, "_download_upstox",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("should not reach")))
    rows = universe.load_universe(market="NSE", prefer_live=True)
    assert len(rows) == 100
    universe.load_universe.cache_clear()
