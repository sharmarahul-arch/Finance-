"""Favourites persistence tests (temp file, no real home dir touched)."""

import pytest

from stock_analyzer import favourites as fav


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(fav, "_PATH", str(tmp_path / "favs.json"))
    # Ensure tests run in local mode regardless of ambient env / prior configure().
    monkeypatch.setattr(fav, "_CONFIG",
                        {"supabase_url": None, "supabase_key": None,
                         "table": "favourites", "user": "default"})
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
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
    # Point at an unwritable path; add should not raise.
    monkeypatch.setattr(fav, "_PATH", "/proc/should-not-be-writable/favs.json")
    fav.add_favourite("X", "NSE", "X")  # must not raise


def test_storage_mode_local_by_default():
    assert fav.storage_mode() == "local"


def test_configure_enables_cloud_mode():
    fav.configure(supabase_url="https://x.supabase.co", supabase_key="key123")
    assert fav.storage_mode() == "cloud"


def test_cloud_read_failure_falls_back_to_local(monkeypatch):
    fav.add_favourite("LOCAL1", "NSE", "Local One")   # written locally
    fav.configure(supabase_url="https://x.supabase.co", supabase_key="key123")
    monkeypatch.setattr(fav, "_sb_read",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network")))
    # Cloud read fails -> must fall back to the local file, not crash.
    favs = fav.load_favourites()
    assert any(f["symbol"] == "LOCAL1" for f in favs)


def test_check_connection_local_mode():
    status = fav.check_connection()
    assert status["mode"] == "local"
    assert status["ok"] is None


def test_check_connection_cloud_ok(monkeypatch):
    fav.configure(supabase_url="https://x.supabase.co", supabase_key="key123")
    monkeypatch.setattr(fav, "_sb_read", lambda cfg: [{"symbol": "TCS", "exchange": "NSE"}])
    status = fav.check_connection()
    assert status["mode"] == "cloud" and status["ok"] is True


def test_check_connection_cloud_error(monkeypatch):
    fav.configure(supabase_url="https://x.supabase.co", supabase_key="key123")
    monkeypatch.setattr(fav, "_sb_read",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("401 unauthorized")))
    status = fav.check_connection()
    assert status["mode"] == "cloud" and status["ok"] is False
    assert "401" in status["message"]


def test_cloud_add_failure_falls_back_to_local(monkeypatch):
    fav.configure(supabase_url="https://x.supabase.co", supabase_key="key123")
    monkeypatch.setattr(fav, "_sb_add",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network")))
    monkeypatch.setattr(fav, "_sb_read",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network")))
    fav.add_favourite("FALLBK", "NSE", "Fallback")    # cloud fails -> local
    assert fav.is_favourite("FALLBK", "NSE")
