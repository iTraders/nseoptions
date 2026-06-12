# -*- encoding: utf-8 -*-

"""
FastAPI Application - REST + WebSocket + Static SPA

Wires the option chain service, history store and suggester behind a thin
HTTP/WebSocket surface and (in production) serves the built ReactJS bundle
as static files from the same origin.

The application lifespan owns the singletons: it opens the SQLite history
store, constructs the :class:`OptionChainService`, primes the NSE cookies
and launches the single background poll task; everything is torn down
cleanly on shutdown.

@author:  Debmalya Pramanik
@version: v0.0.1
@copywright: 2024; Debmalya Pramanik
"""

import os
import asyncio

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from nseoptions.dashboard import schemas, analytics, suggester
from nseoptions.dashboard.history import HistoryStore
from nseoptions.dashboard.settings import AppSettings
from nseoptions.dashboard.service import OptionChainService, NoDataError


def _require_chain(service : OptionChainService, expiry : str | None) -> schemas.ChainOut:
    """Build a chain or raise a 503 while the first poll is still pending."""

    try:
        return service.build_chain(expiry)
    except NoDataError:
        raise HTTPException(status_code = 503, detail = "option chain not ready yet")


def create_app(settings : AppSettings) -> FastAPI:
    """Construct the FastAPI application for the given runtime settings."""

    @asynccontextmanager
    async def lifespan(app : FastAPI):
        # ! own the singletons here so they share one event loop + lifecycle
        store   = HistoryStore(settings.db_path, settings.symbol)
        service = OptionChainService(settings, history = store)

        app.state.settings  = settings
        app.state.history   = store
        app.state.service   = service
        app.state.suggester = suggester.RulesBasedSuggester()

        await service.prime() # setconfig + nse anti-bot cookie priming
        task = asyncio.create_task(service.poll_forever())

        try:
            yield
        finally:
            service.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            store.close()

    app = FastAPI(title = "NSE Options Dashboard", version = "v0.0.1", lifespan = lifespan)

    # ? cors is only needed when the vite dev server is a different origin
    if settings.dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins = [settings.dev_origin],
            allow_methods = ["*"], allow_headers = ["*"]
        )

    # -------------------------- REST endpoints -------------------------- #

    @app.get("/api/health", response_model = schemas.HealthOut)
    async def health(request : Request) -> schemas.HealthOut:
        return request.app.state.service.health()

    @app.get("/api/meta", response_model = schemas.MetaOut)
    async def meta(request : Request) -> schemas.MetaOut:
        return request.app.state.service.build_meta()

    @app.get("/api/chain", response_model = schemas.ChainOut)
    async def chain(request : Request, expiry : str | None = None) -> schemas.ChainOut:
        return _require_chain(request.app.state.service, expiry)

    @app.get("/api/history", response_model = schemas.HistoryOut)
    async def history(
        request : Request,
        expiry  : str,
        strike  : float,
        leg     : str = "CE",
        field   : str = "ltp",
        since   : str | None = None
    ) -> schemas.HistoryOut:
        store = request.app.state.history
        return await asyncio.to_thread(store.series, expiry, strike, leg, field, since)

    @app.get("/api/analytics", response_model = schemas.AnalyticsOut)
    async def analytics_route(request : Request, expiry : str | None = None) -> schemas.AnalyticsOut:
        service = request.app.state.service
        snapshot = _require_chain(service, expiry)
        return analytics.build_analytics(
            service.response, service.symbol, snapshot.expiry, snapshot.underlying
        )

    @app.post("/api/strategy/payoff", response_model = schemas.PayoffOut)
    async def strategy_payoff(request : Request, body : schemas.PayoffIn) -> schemas.PayoffOut:
        service  = request.app.state.service
        snapshot = _require_chain(service, body.expiry)
        return analytics.payoff(
            body.legs, snapshot.underlying, snapshot.expiry,
            lot_size = analytics.lot_size(service.symbol), lots = body.lots,
            rate = settings.rate, quotes = analytics.quote_lookup(snapshot)
        )

    @app.get("/api/suggestions", response_model = schemas.SuggestionsOut)
    async def suggestions(request : Request, expiry : str | None = None) -> schemas.SuggestionsOut:
        service  = request.app.state.service
        snapshot = _require_chain(service, expiry)
        analytic = analytics.build_analytics(
            service.response, service.symbol, snapshot.expiry, snapshot.underlying
        )
        context = suggester.build_context(snapshot, analytic, rate = settings.rate)
        ranked  = request.app.state.suggester.suggest(context)
        return schemas.SuggestionsOut(
            symbol = service.symbol, expiry = snapshot.expiry,
            context = context.summary(), suggestions = ranked
        )

    # --------------------------- WebSocket ------------------------------ #

    @app.websocket("/ws")
    async def websocket(websocket : WebSocket, expiry : str | None = None) -> None:
        service = websocket.app.state.service
        await service.connect(websocket, expiry)

        try:
            while True:
                message = await websocket.receive_json()
                kind = message.get("type")

                if kind == "subscribe":
                    service.set_expiry(websocket, message.get("expiry"))
                    await service.push_current(websocket)
                elif kind == "ping":
                    await websocket.send_json({"type" : "status", "state" : service.health().status})
        except WebSocketDisconnect:
            service.disconnect(websocket)
        except Exception:
            # ! malformed frame / transport error -> drop the client cleanly
            service.disconnect(websocket)

    # ----------------------- static SPA / fallback ---------------------- #

    if not settings.dev and os.path.isdir(settings.static_dir):
        # ! mount LAST so /api and /ws always win; html=True enables the
        # ! client-side router to resolve deep links to index.html
        app.mount("/", StaticFiles(directory = settings.static_dir, html = True), name = "spa")
    else:
        @app.get("/")
        async def root() -> dict:
            return {
                "message"   : "NSE Options Dashboard API",
                "docs"      : "/docs",
                "spa_built" : os.path.isdir(settings.static_dir)
            }

    return app
