# -*- encoding: utf-8 -*-

"""Tests for the option chain assembly + cache (offline, fixture-driven)."""

import asyncio

from nseoptions.dashboard import service
from nseoptions.dashboard.history import HistoryStore
from nseoptions.dashboard.settings import AppSettings
from nseoptions.dashboard.service import OptionChainService


class _FakeWebSocket:
    """Minimal async WebSocket double recording the messages it receives."""

    def __init__(self) -> None:
        self.sent = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data : dict) -> None:
        self.sent.append(data)


def test_assemble_chain_rows(sample, expiry):
    chain = service.assemble_chain(sample, "NIFTY", expiry, nstrikes = 20)

    assert chain.symbol == "NIFTY"
    assert chain.expiry == expiry
    assert chain.atm == 23450.0
    assert chain.multiple == 50
    assert len(chain.rows) == 41            # 2 * nstrikes + 1
    assert sum(1 for row in chain.rows if row.is_atm) == 1
    assert chain.put_call_ratio > 1.0       # the fixture is put-heavy


def test_multi_expiry_from_one_response(sample):
    chain = service.assemble_chain(sample, "NIFTY", "31-Jul-2025", nstrikes = 10)

    assert chain.expiry == "31-Jul-2025"
    assert len(chain.rows) == 21


def test_resolve_expiry_defaults_to_nearest(sample):
    assert service.assemble_chain(sample, "NIFTY", None, 20).expiry == "26-Jun-2025"
    assert service.assemble_chain(sample, "NIFTY", "bogus", 20).expiry == "26-Jun-2025"


def test_degraded_zero_oi_path(closed, expiry):
    chain = service.assemble_chain(closed, "NIFTY", expiry, nstrikes = 15)

    assert chain.put_call_ratio == 0.0      # guarded division, no raise
    assert chain.tot_oi_ce == 0.0
    assert len(chain.rows) > 0


def test_tick_builds_persists_and_broadcasts(tmp_path, monkeypatch, sample, expiry):
    import nseoptions.dashboard.settings as settings_module

    monkeypatch.setattr(settings_module, "BASE_DIR", str(tmp_path)) # sqlite -> tmp

    settings = AppSettings(symbol = "NIFTY", expiry = expiry)
    store = HistoryStore(settings.db_path, "NIFTY")
    svc = OptionChainService(settings, history = store)
    svc._response = sample # seed the cache directly, bypassing the poller

    websocket = _FakeWebSocket()

    async def drive():
        await svc.connect(websocket, expiry) # registers + sends the snapshot
        await svc._tick(sample)              # build off-loop, persist + fan out

    asyncio.run(drive())

    types = [message["type"] for message in websocket.sent]
    assert "snapshot" in types and "tick" in types

    series = store.series(expiry, 23450.0, "CE", "ltp")
    assert len(series.points) == 1 # the primary expiry was persisted
    store.close()
