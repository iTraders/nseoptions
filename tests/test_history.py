# -*- encoding: utf-8 -*-

"""Tests for the SQLite per-strike history store (idempotency + durability)."""

from nseoptions.dashboard import service, history


def _chain(sample, expiry):
    return service.assemble_chain(sample, "NIFTY", expiry, nstrikes = 20)


def test_write_then_series_round_trip(tmp_path, sample, expiry):
    store = history.HistoryStore(str(tmp_path / "sub" / "NIFTY.sqlite3"), "NIFTY")

    written = store.write(_chain(sample, expiry))
    assert written > 0

    series = store.series(expiry, 23450.0, "CE", "ltp")
    assert len(series.points) == 1 and series.field == "ltp"
    store.close()


def test_duplicate_tick_is_idempotent(tmp_path, sample, expiry):
    store = history.HistoryStore(str(tmp_path / "NIFTY.sqlite3"), "NIFTY")
    chain = _chain(sample, expiry)

    store.write(chain)
    store.write(chain) # same timestamp -> INSERT OR IGNORE

    assert len(store.series(expiry, 23450.0, "PE", "oi").points) == 1
    store.close()


def test_history_survives_reopen(tmp_path, sample, expiry):
    path = str(tmp_path / "NIFTY.sqlite3")

    first = history.HistoryStore(path, "NIFTY")
    first.write(_chain(sample, expiry))
    first.close()

    second = history.HistoryStore(path, "NIFTY")
    assert len(second.series(expiry, 23450.0, "PE", "oi").points) == 1
    second.close()


def test_series_field_is_allowlisted(tmp_path, sample, expiry):
    store = history.HistoryStore(str(tmp_path / "NIFTY.sqlite3"), "NIFTY")
    store.write(_chain(sample, expiry))

    # ! an unknown / injection-y field falls back to the safe `ltp` column
    out = store.series(expiry, 23450.0, "CE", "ltp; DROP TABLE option_history")
    assert out.field == "ltp"
    store.close()
