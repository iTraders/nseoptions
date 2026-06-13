# -*- encoding: utf-8 -*-

"""
Application Settings for the NSE Options Dashboard

A small, immutable settings container that bundles the runtime controls
(symbol, expiry, host/port, poll interval, ...) parsed from the command
line by :file:`dashboard.py` and consumed by the FastAPI application and
the option chain service.

The settings object is intentionally frozen - the configuration is
resolved once at boot and never mutated while the server is running.

@author:  Debmalya Pramanik
@version: v0.0.1
@copywright: 2024; Debmalya Pramanik
"""

import os # miscellaneous os interfaces, path manipulations

from dataclasses import dataclass

import nseoptions # registers ROOT/CONFIG, exposes the public api

from nseoptions.worker import DEFAULT_SYMBOLS # the v1 index download universe

# ! the repository base directory is the parent of the package root,
# ! this is where the (git-ignored) `output/` directory already lives
BASE_DIR = os.path.dirname(nseoptions.ROOT)


@dataclass(frozen = True)
class AppSettings:
    """
    Immutable Runtime Settings for the Dashboard Server

    :type  symbol: str
    :param symbol: The index/stock symbol whose option chain is served.
        The value is always normalized to upper case. Defaults to NIFTY.

    :type  expiry: str or None
    :param expiry: The default expiry (``%d-%b-%Y``) served on boot. When
        :obj:`None` the nearest available expiry is auto-selected.

    Keyword Arguments
    -----------------

        * **host** / **port** (*str* / *int*) - The bind address for the
          uvicorn server. Defaults to ``127.0.0.1:8000``.

        * **verify** (*bool*) - SSL certificate validation while fetching
          from NSE India. Defaults to :obj:`False` (matches the package).

        * **interval** (*int*) - The poll interval, in seconds, of the
          single background NSE poller. Defaults to 30.

        * **nstrikes** (*int*) - Strikes above/below the ATM to serve to
          the chain table. Defaults to 20.

        * **dev** (*bool*) - Enable CORS for the Vite dev server and skip
          mounting the built SPA. Defaults to :obj:`False`.

        * **symbols** (*tuple*) - The catalogue of symbols the dashboard
          may download via the ``Fetch Data`` control. Defaults to the v1
          index universe (:data:`nseoptions.worker.DEFAULT_SYMBOLS`).

        * **max_concurrent** (*int*) - The cap on concurrent NSE fetches
          shared across every download worker. Defaults to 3.
    """

    symbol     : str = "NIFTY"
    expiry     : str | None = None
    host       : str = "127.0.0.1"
    port       : int = 8000
    verify     : bool = False
    interval   : int = 30
    nstrikes   : int = 20
    dev        : bool = False

    # ? asynchronous downloader controls - the "Fetch Data" universe and
    # ? the shared concurrency cap consumed by the download manager
    symbols        : tuple = DEFAULT_SYMBOLS
    max_concurrent : int = 3

    # ? transport + analytics tunables, sensible defaults for india
    timeout    : int = 12     # per-request timeout (seconds) for the nse fetch
    waittime   : int = 5      # core.response() retry wait on the fallback path
    rate       : float = 0.065 # risk-free rate used by the black-scholes greeks
    dev_origin : str = "http://localhost:5173" # vite dev server origin (cors)

    @property
    def db_path(self) -> str:
        # ? per-symbol sqlite history file under the existing output dir
        return os.path.join(BASE_DIR, "output", "history", f"{self.symbol}.sqlite3")

    @property
    def static_dir(self) -> str:
        # ? the built react bundle, served by the backend in production
        return os.path.join(nseoptions.ROOT, "dashboard", "frontend", "dist")
