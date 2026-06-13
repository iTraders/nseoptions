# -*- encoding: utf-8 -*-

"""
Tests for the Download Controls - Symbols Catalogue and Fetch Manager

Exercises the new "Fetch Data" surface entirely offline: the REST
catalogue and idle status routes via the seeded ``TestClient``, and the
:class:`nseoptions.dashboard.downloader.DownloadManager` lifecycle with
the network expiry discovery and the per-expiry worker patched out.

@author:  Debmalya Pramanik
@version: v0.0.1
"""

import asyncio

from unittest.mock import patch

from nseoptions.dashboard import downloader
from nseoptions.dashboard.settings import AppSettings


def test_symbols_endpoint_lists_index_universe(client) -> None:
    reply = client.get("/api/symbols")
    assert reply.status_code == 200

    body = reply.json()
    names = [item["symbol"] for item in body["symbols"]]
    multiples = {item["symbol"] : item["multiple"] for item in body["symbols"]}

    assert "NIFTY" in names and "BANKNIFTY" in names
    assert multiples["NIFTY"] == 50 and multiples["BANKNIFTY"] == 100
    assert body["default"] == names


def test_fetch_status_is_idle_before_start(client) -> None:
    reply = client.get("/api/fetch/status")
    assert reply.status_code == 200

    body = reply.json()
    assert body["running"] is False
    assert body["workers"] == []


def test_download_manager_start_then_stop() -> None:
    async def fake_worker(
        symbol    : str,
        expiry    : str,
        semaphore : object,
        sink      : object,
        *,
        on_status : object = None,
        **kwargs
    ) -> None:
        await sink(symbol, expiry, {"records" : {"timestamp" : "t1"}}, None, None)
        if on_status:
            on_status(symbol, expiry, state = "ok", timestamp = "t1")
        await asyncio.Event().wait() # idle until cancelled by stop()

    class FakeAPI:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def expiries(self) -> list:
            return ["26-Jun-2025", "03-Jul-2025"]

    async def scenario() -> object:
        settings = AppSettings(symbols = ("NIFTY",), max_concurrent = 2)
        manager = downloader.DownloadManager(settings)

        await manager.start(["NIFTY"])
        await asyncio.sleep(0.05) # let the bootstrap discover + spawn

        snapshot = manager.status()
        await manager.stop()
        return snapshot, manager

    with patch.object(downloader, "NSEOptionChain", FakeAPI), \
         patch.object(downloader.worker, "symbol_worker", fake_worker):
        status, manager = asyncio.run(scenario())

    assert status.running is True
    assert {item.expiry for item in status.workers} == {"26-Jun-2025", "03-Jul-2025"}
    assert all(item.state == "ok" and item.snapshots == 1 for item in status.workers)
    assert manager.running is False and manager._tasks == {}


def test_worker_survives_null_records_payload() -> None:
    from nseoptions import worker

    class NullRecordsAPI:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def setexpiry(self, expiry : str) -> str:
            return expiry

        def response(self, waittime : int, maxretries : int) -> dict:
            return {"records" : None, "filtered" : None}

    async def sink(*args) -> None:
        return None

    async def scenario() -> bool:
        semaphore = asyncio.Semaphore(1)
        with patch.object(worker, "NSEOptionChain", NullRecordsAPI):
            task = asyncio.create_task(worker.symbol_worker(
                "NIFTY", "26-Jun-2025", semaphore, sink, interval = 0
            ))
            await asyncio.sleep(0.05) # let the loop spin past the null read
            alive = not task.done()

            task.cancel()
            await asyncio.gather(task, return_exceptions = True)
            return alive

    # ! a null `records` must not kill the worker (it used to raise an
    # ! AttributeError in the unguarded gap between the two try blocks)
    assert asyncio.run(scenario()) is True
