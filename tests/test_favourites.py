"""Favourites persistence tests (temp file, no real home dir touched)."""

import pytest

from stock_analyzer import favourites as fav


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(fav, "_PATH", str(tmp_path / "favs.json"))
    yield


def test_add_and_query():
    assert fav.load_favourites() == []
    fav.add_favourite("RELIANCE", "NSE", "Reliance Industries")
    assert fav.is_favourite("reliance", "nse")          # case-insensitive
    favs = fav.load_favourites()
    assert len(favs) == 1
    assert favs[0]["symbol"] == "RELIANCE"


def test_add_is_idempotent():
    fav.add_favourite("TCS", "NSE", "TCS")
    fav.add_favourite("TCS", "NSE", "TCS")
    assert len(fav.load_favourites()) == 1


def test_same_symbol_different_exchange_kept_separate():
    fav.add_favourite("RELIANCE", "NSE", "Reliance")
    fav.add_favourite("RELIANCE", "BSE", "Reliance")
    assert len(fav.load_favourites()) == 2
    assert len(fav.load_favourites("NSE")) == 1
    assert len(fav.load_favourites("BSE")) == 1


def test_remove():
    fav.add_favourite("INFY", "NSE", "Infosys")
    fav.remove_favourite("INFY", "NSE")
    assert not fav.is_favourite("INFY", "NSE")


def test_toggle():
    assert fav.toggle_favourite("WIPRO", "NSE", "Wipro") is True
    assert fav.is_favourite("WIPRO", "NSE")
    assert fav.toggle_favourite("WIPRO", "NSE", "Wipro") is False
    assert not fav.is_favourite("WIPRO", "NSE")


def test_persists_across_reload():
    fav.add_favourite("ITC", "NSE", "ITC")
    # A fresh read (simulating a new session) sees the saved favourite.
    assert fav.is_favourite("ITC", "NSE")


def test_readonly_filesystem_does_not_crash(monkeypatch):
    def _boom(*a, **k):
        raise OSError("read-only fs")
    monkeypatch.setattr(fav, "_save", _boom if False else fav._save)
    # Point at an unwritable path; add should not raise.
    monkeypatch.setattr(fav, "_PATH", "/proc/should-not-be-writable/favs.json")
    fav.add_favourite("X", "NSE", "X")  # must not raise
