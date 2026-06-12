# -*- encoding: utf-8 -*-

"""
Shared Pytest Fixtures

Loads the committed, offline NSE payloads and exposes a network-free
FastAPI ``TestClient`` whose option chain service is seeded directly from
the sample fixture (the cookie priming and the background poller are
patched out) so the entire suite runs without ever touching NSE.

@author:  Debmalya Pramanik
@version: v0.0.1
"""

import os
import json
import datetime as dt

import pytest

from nseoptions.dashboard import analytics
from nseoptions.dashboard.settings import AppSettings
from nseoptions.dashboard.service import OptionChainService

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# ? the front-month expiry of the fixtures + an "as-of" anchor matching
# ? the fixture timestamp, so greeks/DTE are deterministic across runs
EXPIRY = "26-Jun-2025"
ASOF   = dt.datetime(2025, 6, 13, 9, 15, tzinfo = analytics.IST)


def _load(name : str) -> dict:
    with open(os.path.join(FIXTURES, name)) as handle:
        return json.load(handle)


@pytest.fixture
def sample() -> dict:
    return _load("nse_nifty_sample.json")


@pytest.fixture
def closed() -> dict:
    return _load("nse_market_closed.json")


@pytest.fixture
def expiry() -> str:
    return EXPIRY


@pytest.fixture
def asof() -> dt.datetime:
    return ASOF


@pytest.fixture
def client(monkeypatch, tmp_path, sample):
    """A TestClient whose service is seeded from the fixture (no network)."""

    from fastapi.testclient import TestClient

    import nseoptions.dashboard.settings as settings_module
    from nseoptions.dashboard.server import create_app

    async def fake_prime(self) -> None:
        self._response = sample
        self._fetched_at = dt.datetime.now()
        self._status, self._detail = "live", None

    async def fake_poll(self) -> None:
        return # ! no background NSE polling during tests

    monkeypatch.setattr(OptionChainService, "prime", fake_prime)
    monkeypatch.setattr(OptionChainService, "poll_forever", fake_poll)
    monkeypatch.setattr(settings_module, "BASE_DIR", str(tmp_path)) # sqlite -> tmp

    app = create_app(AppSettings(symbol = "NIFTY", expiry = EXPIRY, nstrikes = 20))
    with TestClient(app) as test_client:
        yield test_client
