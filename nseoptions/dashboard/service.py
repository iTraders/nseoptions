# -*- encoding: utf-8 -*-

"""
Option Chain Service - Single Poller, Cache and WebSocket Fan-Out

The service is the single source of truth for the dashboard. Exactly one
background task polls NSE on a fixed interval, caches the latest raw
payload in-memory, persists per-strike history and broadcasts the
processed snapshot to every connected WebSocket client. New clients are
served the cached snapshot immediately and never trigger a fresh fetch -
the only NSE traffic is the lone poller.

The locked data module (:mod:`nseoptions.core`/:mod:`nseoptions.processing`)
is consumed as-is. Because :meth:`core.NSEOptionChain.response` opens a
fresh, cookie-less ``requests.Session`` on every call, this service owns
its own persistent session and primes the NSE anti-bot cookies before
reusing the public ``NSE_API_URI``/``URI_HEADER`` that ``setconfig`` built.

@author:  Debmalya Pramanik
@version: v0.0.1
@copywright: 2024; Debmalya Pramanik
"""

import time     # wall-clock timestamps for status and logging
import random   # poll-interval jitter to avoid a fixed request cadence
import asyncio  # async poller loop and websocket broadcast
import datetime as dt # control and perceive the runtime environment

import requests # persistent session for nse anti-bot cookie priming

import nseoptions # public api: NSEOptionChain + processing

from nseoptions.dashboard import schemas
from nseoptions.dashboard.settings import AppSettings

# ? the leg numeric fields, shared with the schema/contract definition
LEG_FIELDS = schemas.LEG_FIELDS

# ? nse landing pages used to prime the anti-bot cookies before the api
NSE_HOMEPAGE = "https://www.nseindia.com"
NSE_REFERER  = "https://www.nseindia.com/option-chain"


class NoDataError(RuntimeError):
    """Raised when a snapshot is requested before the first poll."""
    pass


def _num(value : object) -> float:
    """Coerce a value to ``float``, mapping NaN/None/blank to ``0.0``."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0

    return number if number == number else 0.0 # ! NaN is never equal to itself


def resolve_expiry(response : dict, expiry : str | None) -> str | None:
    """Return a valid expiry, defaulting to the nearest available one."""

    expiries = response.get("records", {}).get("expiryDates", []) or []

    if expiry and expiry in expiries:
        return expiry # honour an explicit, valid selection

    return expiries[0] if expiries else expiry # nearest, else trust caller


def _leg_quote(record : dict, suffix : str) -> schemas.LegQuote:
    """Assemble a :class:`schemas.LegQuote` from a merged frame record."""

    return schemas.LegQuote(**{
        field : _num(record.get(f"{field}_{suffix}")) for field in LEG_FIELDS
    })


def _leg_from_raw(leg : dict) -> schemas.LegQuote:
    """Assemble a :class:`schemas.LegQuote` straight from a raw NSE leg."""

    return schemas.LegQuote(**{
        field : _num(leg.get(field)) for field in LEG_FIELDS
    })


def _rows_from_raw(response : dict, model : object, expiry : str) -> list:
    """
    Fallback row builder for the degraded (zero open-interest) path.

    When the market is closed NSE reports a zero ``totOI`` which makes
    :meth:`makeclean` raise on the put-call-ratio division. In that case
    the rows are rebuilt directly from the raw records over the same
    strike window the model already computed.
    """

    legs : dict = {} # strikePrice -> {"CE": LegQuote, "PE": LegQuote}
    for item in response.get("records", {}).get("data", []):
        if item.get("expiryDate") != expiry:
            continue

        strike = _num(item.get("strikePrice"))
        if not (model.lstrike <= strike <= model.hstrike):
            continue

        bucket = legs.setdefault(strike, {})
        for side in ("CE", "PE"):
            if side in item:
                bucket[side] = _leg_from_raw(item[side])

    rows = []
    for strike in sorted(legs):
        bucket = legs[strike]
        rows.append(schemas.StrikeRow(
            strikePrice = strike,
            ce = bucket.get("CE"),
            pe = bucket.get("PE"),
            is_atm = strike == _num(model.atm)
        ))

    return rows


def assemble_chain(
    response : dict,
    symbol   : str,
    expiry   : str | None,
    nstrikes : int = 20
) -> schemas.ChainOut:
    """
    Build a :class:`schemas.ChainOut` for one expiry from a raw response.

    The processed table, totals and put-call-ratio come from the locked
    :class:`nseoptions.processing.OptionChainProcessing` api. A degraded
    path rebuilds the rows from the raw records when the market is closed.
    """

    expiry = resolve_expiry(response, expiry)

    # ? the constructor is free of the division side-effect; it gives us
    # ? the atm/strike-range, multiple, underlying and timestamp safely
    model = nseoptions.processing.OptionChainProcessing(
        symbol, apikey = "", response = response,
        expiry = expiry, nstrikes = nstrikes
    )

    underlying = _num(model.underlying)
    timestamp  = model.timestamp.isoformat()

    try:
        frame = model.makeclean() # locked api: 29-col CE | strike | PE
        rows  = [
            schemas.StrikeRow(
                strikePrice = _num(record["strikePrice"]),
                ce = _leg_quote(record, "ce"),
                pe = _leg_quote(record, "pe"),
                is_atm = _num(record["strikePrice"]) == _num(model.atm)
            )
            for record in frame.to_dict("records")
        ]

        pcr        = _num(model.put_call_ratio)
        tot_oi_ce  = _num(model.tot_oi_ce)
        tot_oi_pe  = _num(model.tot_oi_pe)
        tot_vol_ce = _num(model.tot_vol_ce)
        tot_vol_pe = _num(model.tot_vol_pe)
    except ZeroDivisionError:
        # ! market closed / zero open-interest -> rebuild from raw records
        rows = _rows_from_raw(response, model, expiry)

        filtered   = response.get("filtered", {})
        tot_oi_ce  = _num(filtered.get("CE", {}).get("totOI"))
        tot_oi_pe  = _num(filtered.get("PE", {}).get("totOI"))
        tot_vol_ce = _num(filtered.get("CE", {}).get("totVol"))
        tot_vol_pe = _num(filtered.get("PE", {}).get("totVol"))
        pcr        = tot_oi_pe / tot_oi_ce if tot_oi_ce else 0.0

    return schemas.ChainOut(
        symbol = symbol, expiry = expiry,
        underlying = underlying, timestamp = timestamp,
        atm = _num(model.atm), multiple = int(model.multiple),
        put_call_ratio = pcr,
        tot_oi_ce = tot_oi_ce, tot_oi_pe = tot_oi_pe,
        tot_vol_ce = tot_vol_ce, tot_vol_pe = tot_vol_pe,
        rows = rows
    )


class OptionChainService:
    """
    Single-Poller Option Chain Service with Live Fan-Out

    Owns one :class:`nseoptions.NSEOptionChain` session, polls on a fixed
    interval, caches the latest raw payload in-memory and broadcasts the
    processed snapshot to every connected WebSocket client.

    :type  settings: AppSettings
    :param settings: The immutable runtime settings for the server.

    :type  history: object
    :param history: An optional, duck-typed history store exposing a
        ``write(chain)`` method. When :obj:`None` history is not recorded.
    """

    def __init__(self, settings : AppSettings, history : object = None) -> None:
        self.settings = settings
        self.symbol   = settings.symbol.upper()

        # ? the locked core api object, primed once and reused each poll
        self._api = nseoptions.NSEOptionChain(self.symbol, verify = settings.verify)

        # ! our own persistent session holds the nse anti-bot cookies that
        # ! the (sessionless) core.response() never captures on its own
        self._session = requests.Session()

        self._history = history # duck-typed store, optional

        self._response   : dict | None = None # latest raw nse payload
        self._fetched_at : dt.datetime | None = None
        self._status     : str = "starting"
        self._detail     : str | None = None

        self._clients : dict = {} # websocket -> subscribed expiry
        self._stopped : bool = False


    # -------- lifecycle: priming + the background poll loop -------- #

    async def prime(self) -> None:
        """Run ``setconfig()`` and the cookie-priming GET, off the loop."""

        await asyncio.to_thread(self._api.setconfig)
        await asyncio.to_thread(self._prime_cookies)


    def _prime_cookies(self) -> None:
        """Visit the NSE landing pages to capture the anti-bot cookies."""

        headers = dict(self._api.URI_HEADER)
        try:
            for url in (NSE_HOMEPAGE, NSE_REFERER):
                self._session.get(
                    url, headers = headers,
                    timeout = self.settings.timeout, verify = self.settings.verify
                )
        except Exception as e:
            print(f"{time.ctime()} : Cookie Priming Failed - {e}")


    def _fetch_once(self) -> dict:
        """
        Blocking single fetch using the primed session.

        Reuses the public ``NSE_API_URI``/``URI_HEADER`` built by the
        locked ``setconfig``. On any failure it re-primes the cookies and
        falls back to the core retry-loop fetch as a last resort.
        """

        headers = dict(self._api.URI_HEADER)
        headers.setdefault("accept", "*/*")
        headers.setdefault("referer", NSE_REFERER)

        try:
            reply = self._session.get(
                self._api.NSE_API_URI, headers = headers,
                timeout = self.settings.timeout, verify = self.settings.verify
            )
            reply.raise_for_status()

            payload = reply.json()
            if not payload.get("records"):
                raise ValueError("empty or blocked nse response")

            return payload
        except Exception as e:
            # ! primed path failed (cookie expiry/block) -> reprime + fallback
            print(f"{time.ctime()} : Primed Fetch Failed - {e}; using core fallback")
            self._prime_cookies()

            payload = self._api.response(waittime = self.settings.waittime)
            if not payload.get("records"):
                # ! never cache a records-less payload (turns 503s into 500s)
                raise ValueError("empty or blocked nse fallback response")
            return payload


    async def poll_forever(self) -> None:
        """Background task: fetch -> cache -> persist -> broadcast, forever."""

        while not self._stopped:
            try:
                payload = await asyncio.to_thread(self._fetch_once)

                self._response   = payload
                self._fetched_at = dt.datetime.now()
                self._status, self._detail = "live", None

                await self._tick(payload) # build off-loop, persist + fan out
            except Exception as e:
                self._status, self._detail = "degraded", str(e)
                print(f"{time.ctime()} : Poll Error - {e}")
                await self._broadcast_status()

            await asyncio.sleep(self._jitter(self.settings.interval))


    def stop(self) -> None:
        """Signal the poll loop to exit at the next iteration."""

        self._stopped = True


    @staticmethod
    def _jitter(interval : int) -> float:
        """Add a small random jitter so requests are not perfectly periodic."""

        return interval + random.uniform(0, min(5, interval * 0.2))


    # -------- snapshot builders served to REST + WebSocket -------- #

    def build_chain(self, expiry : str | None = None) -> schemas.ChainOut:
        """Build a processed chain for an expiry from the cached response."""

        if self._response is None:
            raise NoDataError("option chain not fetched yet")

        return assemble_chain(
            self._response, self.symbol, expiry, self.settings.nstrikes
        )


    def build_meta(self) -> schemas.MetaOut:
        """Return expiries, status and the strike multiple/window bounds."""

        expiries : list = []
        underlying = timestamp = multiple = None
        expiry = self.settings.expiry

        if self._response is not None:
            records    = self._response.get("records", {})
            expiries   = records.get("expiryDates", []) or []
            underlying = _num(records.get("underlyingValue"))
            timestamp  = records.get("timestamp")
            expiry     = resolve_expiry(self._response, self.settings.expiry)

            # ? reuse the locked imultiple via a throwaway model instance
            model = nseoptions.processing.OptionChainProcessing(
                self.symbol, apikey = "", response = self._response,
                expiry = expiry, nstrikes = self.settings.nstrikes
            )
            multiple = int(model.multiple)

        return schemas.MetaOut(
            symbol = self.symbol, expiries = expiries, expiry = expiry,
            multiple = multiple, nstrikes = self.settings.nstrikes,
            status = self._status, detail = self._detail,
            underlying = underlying, timestamp = timestamp
        )


    def health(self) -> schemas.HealthOut:
        """Liveness probe: status, last poll time and live client count."""

        return schemas.HealthOut(
            status = self._status, symbol = self.symbol,
            last_poll = self._fetched_at.isoformat() if self._fetched_at else None,
            clients = len(self._clients)
        )


    @property
    def response(self) -> dict | None:
        """The latest cached raw NSE payload (used by analytics)."""

        return self._response


    async def _tick(self, response : dict) -> None:
        """
        Process one poll: build the needed snapshots in a worker thread,
        persist the primary one and broadcast to every client.

        All pandas work (``makeclean``) and the SQLite write are offloaded
        via :func:`asyncio.to_thread` so the event loop (and thus every
        other client + HTTP route) is never blocked.
        """

        primary = resolve_expiry(response, self.settings.expiry)
        wanted  = {primary, *self._clients.values()} # distinct expiries to build

        built = await asyncio.to_thread(self._build_many, response, wanted)

        if self._history is not None and built.get(primary) is not None:
            await asyncio.to_thread(self._history.write, built[primary])

        await self._broadcast_built(built, response)


    def _build_many(self, response : dict, expiries : set) -> dict:
        """Assemble chains for several expiries in one worker thread."""

        chains : dict = {}
        for expiry in expiries:
            if not expiry:
                continue
            try:
                chains[expiry] = assemble_chain(
                    response, self.symbol, expiry, self.settings.nstrikes
                )
            except Exception as e:
                print(f"{time.ctime()} : Build Failed for {expiry} - {e}")

        return chains


    # -------- websocket connection management + fan-out -------- #

    async def connect(self, websocket : object, expiry : str | None = None) -> None:
        """Accept a client, register its expiry and send it the snapshot."""

        await websocket.accept()
        self._clients[websocket] = resolve_expiry(self._response or {}, expiry)

        if self._response is None:
            await self._send(websocket, schemas.SocketMessage(
                type = "status", state = self._status, detail = self._detail
            ))
            return

        try:
            chain = await asyncio.to_thread(self.build_chain, self._clients[websocket])
            await self._send(websocket, schemas.SocketMessage(type = "snapshot", chain = chain))
        except Exception as e:
            await self._send(websocket, schemas.SocketMessage(
                type = "status", state = self._status, detail = str(e)
            ))


    def set_expiry(self, websocket : object, expiry : str | None) -> None:
        """Switch a client's subscribed expiry (a pure cache read, no fetch)."""

        if websocket in self._clients:
            self._clients[websocket] = resolve_expiry(self._response or {}, expiry)


    def disconnect(self, websocket : object) -> None:
        """Drop a client from the broadcast set."""

        self._clients.pop(websocket, None)


    async def push_current(self, websocket : object) -> None:
        """Send the current snapshot to a single client (post expiry switch)."""

        if self._response is None:
            return

        try:
            chain = await asyncio.to_thread(self.build_chain, self._clients.get(websocket))
            await self._send(websocket, schemas.SocketMessage(type = "snapshot", chain = chain))
        except Exception:
            self.disconnect(websocket)


    async def _broadcast_built(self, built : dict, response : dict) -> None:
        """Fan out pre-built snapshots to each client by its subscribed expiry."""

        if not self._clients:
            return

        dead : list = []
        for websocket, expiry in list(self._clients.items()):
            chain = built.get(expiry) or built.get(resolve_expiry(response, expiry))
            if chain is None:
                continue
            try:
                await self._send(websocket, schemas.SocketMessage(type = "tick", chain = chain))
            except Exception:
                dead.append(websocket)

        for websocket in dead:
            self.disconnect(websocket)


    async def _broadcast_status(self) -> None:
        """Notify every client of a status change (e.g. degraded feed)."""

        message = schemas.SocketMessage(type = "status", state = self._status, detail = self._detail)
        dead : list = []

        for websocket in list(self._clients):
            try:
                await self._send(websocket, message)
            except Exception:
                dead.append(websocket)

        for websocket in dead:
            self.disconnect(websocket)


    @staticmethod
    async def _send(websocket : object, message : schemas.SocketMessage) -> None:
        """Serialize and send one schema message over a WebSocket."""

        await websocket.send_json(message.model_dump())
