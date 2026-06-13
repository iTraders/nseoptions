# -*- encoding: utf-8 -*-

"""End-to-end API tests via FastAPI TestClient (service seeded, no network)."""


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "live" and body["symbol"] == "NIFTY"


def test_meta(client):
    body = client.get("/api/meta").json()
    assert "26-Jun-2025" in body["expiries"]
    assert body["multiple"] == 50 and body["expiry"] == "26-Jun-2025"


def test_chain(client):
    body = client.get("/api/chain").json()
    assert body["expiry"] == "26-Jun-2025"
    assert len(body["rows"]) == 41
    assert any(row["is_atm"] for row in body["rows"])


def test_chain_other_expiry(client):
    body = client.get("/api/chain", params = {"expiry" : "31-Jul-2025"}).json()
    assert body["expiry"] == "31-Jul-2025"


def test_analytics(client):
    body = client.get("/api/analytics").json()
    assert body["max_pain"] is not None and len(body["iv_smile"]) > 0
    assert body["support"] and body["resistance"]


def test_strategy_payoff(client):
    payload = {
        "symbol" : "NIFTY", "expiry" : "26-Jun-2025", "lots" : 1,
        "legs"   : [{"strike" : 23450, "leg" : "CE", "side" : "BUY", "qty" : 1, "price" : 100.0}]
    }
    body = client.post("/api/strategy/payoff", json = payload).json()
    assert body["max_loss"] == -7500.0
    assert body["max_profit"] is None
    assert body["breakevens"] == [23550.0]


def test_suggestions(client):
    body = client.get("/api/suggestions").json()
    assert body["context"]["bias"] == "bullish"
    assert len(body["suggestions"]) >= 1


def test_history_endpoint_shape(client):
    body = client.get(
        "/api/history",
        params = {"expiry" : "26-Jun-2025", "strike" : 23450, "leg" : "CE", "field" : "ltp"},
    ).json()
    assert body["strike"] == 23450.0 and body["leg"] == "CE" and body["field"] == "ltp"
    assert isinstance(body["points"], list) # empty until the poller records ticks


def test_websocket_snapshot(client):
    with client.websocket_connect("/ws?expiry=26-Jun-2025") as socket:
        message = socket.receive_json()
        assert message["type"] == "snapshot"
        assert message["chain"]["expiry"] == "26-Jun-2025"
        assert len(message["chain"]["rows"]) == 41
