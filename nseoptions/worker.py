# -*- encoding: utf-8 -*-

"""
Asynchronous Per-Expiry NSE Option Chain Download Worker

The module exposes a single reusable coroutine, :func:`symbol_worker`,
that polls the NSE v3 option chain for one ``(symbol, expiry)`` pair in
an infinite loop and hands every freshly observed snapshot to a caller
supplied ``sink``. The worker is the shared unit of work behind both the
dashboard's in-process download manager and the standalone downloader
service, so it deliberately knows nothing about where the data is stored.

The locked :class:`nseoptions.NSEOptionChain` is synchronous and warms up
its own anti-bot session, hence every blocking call (the network fetch and
the :mod:`pandas` ``makeclean``) is off-loaded with :func:`asyncio.to_thread`
to keep the event loop responsive. Persistence is fully decoupled through
the ``sink`` callback - the PostgreSQL writer is wired in there later
without touching this module.

:NOTE: The fetch runs inside the shared ``semaphore`` to bound the number
    of concurrent NSE requests. ``maxretries`` is kept small on purpose so
    a failing fetch releases its semaphore slot quickly and is retried on
    the worker's own loop, rather than starving the other workers.
"""

import asyncio

from typing import Awaitable, Callable

from nseoptions import NSEOptionChain
from nseoptions.processing import OptionChainProcessing

# ? the default index universe for the v1 MVP (equities deferred to v2)
DEFAULT_SYMBOLS = ("NIFTY", "BANKNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "FINNIFTY")

# ? a snapshot sink: async callback invoked once per newly observed chain;
# ? the signature mirrors the eventual db.write_snapshot(...) writer contract
Sink = Callable[[str, str, dict, object, object], Awaitable[None]]


def _report(
    hook   : Callable[..., None] | None,
    symbol : str,
    expiry : str,
    **kwargs
) -> None:
    """
    Invoke the Optional Status Hook, Isolating Hook-Side Failures

    The status hook is a best-effort progress channel for the caller
    (for example the download manager that aggregates worker state).
    A faulty hook must never break the fetch loop, so any exception it
    raises is swallowed here.

    :type  hook: Callable or None
    :param hook: The status callback ``hook(symbol, expiry, **kwargs)``
        or :obj:`None` when the caller does not track status.

    :type  symbol: str
    :param symbol: The symbol the status update refers to.

    :type  expiry: str
    :param expiry: The expiry the status update refers to.

    :rtype:  None
    :return: This function returns nothing.
    """

    if hook is None:
        return

    try:
        hook(symbol, expiry, **kwargs)
    except Exception:
        pass # ! status reporting is best-effort and never breaks the loop


async def symbol_worker(
    symbol     : str,
    expiry     : str,
    semaphore  : asyncio.Semaphore,
    sink       : Sink,
    *,
    verify     : bool = False,
    timeout    : int = 15,
    interval   : int = 30,
    nstrikes   : int = 20,
    waittime   : int = 5,
    maxretries : int = 2,
    on_status  : Callable[..., None] | None = None
) -> None:
    """
    Poll One ``(symbol, expiry)`` Option Chain and Feed the Sink

    The coroutine loops forever - fetch, deduplicate, process and sink -
    until it is cancelled by the caller. A fresh :class:`NSEOptionChain`
    is created per worker so each holds its own warmed-up session (and
    therefore its own anti-bot cookies), matching the isolation the NSE
    API expects. Duplicate snapshots are skipped using the NSE response
    timestamp so an unchanged chain never reaches the ``sink``.

    :type  symbol: str
    :param symbol: The index/stock symbol to poll, for example ``NIFTY``.

    :type  expiry: str
    :param expiry: A valid contract expiry (``%d-%b-%Y``) for the symbol.

    :type  semaphore: asyncio.Semaphore
    :param semaphore: The shared semaphore that bounds the number of
        concurrent NSE fetches across every worker.

    :type  sink: Callable
    :param sink: An async callback ``sink(symbol, expiry, response, model,
        opchain)`` invoked once per newly observed snapshot. This is the
        persistence seam - the PostgreSQL writer is plugged in here.

    **Keyword Arguments**

    The keyword arguments tune the transport and the loop cadence and all
    have sensible defaults that mirror the package and the dashboard.

        * **verify** (*bool*): SSL certificate verification for the NSE
            fetch. Defaults to :obj:`False`, matching the package.

        * **timeout** (*int*): Per-request timeout in seconds. Default 15.

        * **interval** (*int*): Seconds to sleep between two loop turns.
            Default 30, matching the package poll cadence.

        * **nstrikes** (*int*): Strikes above/below the ATM to retain.
            Default 20.

        * **waittime** (*int*): Seconds the locked ``response`` waits
            between its own internal retries. Default 5.

        * **maxretries** (*int*): Cap on the locked ``response`` internal
            retries. Kept small (default 2) so a failing fetch releases
            its semaphore slot quickly and is retried on this loop.

        * **on_status** (*Callable*): Optional best-effort status hook
            ``on_status(symbol, expiry, state=..., detail=..., timestamp=...)``.

    :rtype:  None
    :return: The coroutine only returns when cancelled.
    """

    api = NSEOptionChain(symbol, verify = verify, timeout = timeout)

    # ! build the v3 api uri (and lazily the config) off the event loop
    await asyncio.to_thread(api.setexpiry, expiry)

    last_seen : str | None = None
    while True:
        try:
            async with semaphore:
                response = await asyncio.to_thread(api.response, waittime, maxretries)
        except asyncio.CancelledError:
            raise # ! propagate cancellation so the manager can stop us
        except Exception as exc:
            _report(on_status, symbol, expiry, state = "error", detail = str(exc))
            await asyncio.sleep(interval)
            continue

        # ? skip processing entirely when the chain has not changed yet
        timestamp = response.get("records", {}).get("timestamp")
        if timestamp is not None and timestamp == last_seen:
            await asyncio.sleep(interval)
            continue

        try:
            model = OptionChainProcessing(
                symbol, apikey = "", response = response,
                expiry = expiry, nstrikes = nstrikes
            )
            opchain = await asyncio.to_thread(model.makeclean, verbose = False)
            await sink(symbol, expiry, response, model, opchain)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _report(on_status, symbol, expiry, state = "error", detail = str(exc))
            await asyncio.sleep(interval)
            continue

        last_seen = timestamp
        _report(on_status, symbol, expiry, state = "ok", timestamp = timestamp)
        await asyncio.sleep(interval)
