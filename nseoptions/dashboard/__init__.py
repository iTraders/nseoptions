# -*- encoding: utf-8 -*-

"""
Web Dashboard for the NSE Options Chain Package

A production-grade ReactJS dashboard served by a FastAPI backend. The
backend runs a single NSE poller, caches the option chain in-memory,
persists per-strike history to SQLite, and fans out live updates to the
connected clients over a WebSocket. The built React bundle is served as
static files by the same backend so the whole dashboard boots from a
single command:

    python dashboard.py --symbol NIFTY --port 8000

The :func:`launch` helper is the one public entry point - it builds the
immutable settings and starts the uvicorn server. Heavy imports are kept
lazy so importing this package stays cheap.

@author:  Debmalya Pramanik
@version: v0.0.1
@copywright: 2024; Debmalya Pramanik
"""


def launch(
    symbol         : str = "NIFTY",
    expiry         : str | None = None,
    host           : str = "127.0.0.1",
    port           : int = 8000,
    verify         : bool = False,
    interval       : int = 30,
    nstrikes       : int = 20,
    dev            : bool = False,
    reload         : bool = False,
    symbols        : list | tuple | None = None,
    max_concurrent : int = 3
) -> None:
    """
    Boot the uvicorn server that serves the ReactJS dashboard.

    :type  symbol: str
    :param symbol: The index/stock symbol to serve. Normalized to upper.

    :type  expiry: str or None
    :param expiry: The default expiry served on boot (nearest if None).

    Keyword Arguments
    -----------------

        * **host** / **port** - The uvicorn bind address (127.0.0.1:8000).
        * **verify** (*bool*) - SSL verification for the NSE fetch (False).
        * **interval** (*int*) - The background poll interval in seconds.
        * **nstrikes** (*int*) - Strikes above/below the ATM to serve.
        * **dev** (*bool*) - Enable CORS for the Vite dev server.
        * **reload** (*bool*) - Enable uvicorn auto-reload (development).
        * **symbols** (*list*) - The downloadable symbol universe for the
          "Fetch Data" control. When :obj:`None` the AppSettings default
          (the v1 index universe) is used.
        * **max_concurrent** (*int*) - Cap on concurrent NSE fetches
          shared across the download workers. Defaults to 3.
    """

    import uvicorn # local import keeps the package import cheap

    from nseoptions.dashboard.server import create_app
    from nseoptions.dashboard.settings import AppSettings

    options = dict(
        symbol = symbol.upper(), expiry = expiry,
        host = host, port = port, verify = verify,
        interval = interval, nstrikes = nstrikes, dev = dev,
        max_concurrent = max_concurrent
    )

    # ? only override the symbol universe when the caller supplies one,
    # ? otherwise the immutable AppSettings default (indices) applies
    if symbols:
        options["symbols"] = tuple(sym.upper() for sym in symbols)

    settings = AppSettings(**options)

    app = create_app(settings)
    uvicorn.run(app, host = settings.host, port = settings.port, reload = reload)
