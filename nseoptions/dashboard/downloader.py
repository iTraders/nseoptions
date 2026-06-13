# -*- encoding: utf-8 -*-

"""
In-Process Asynchronous Option Chain Download Manager

The manager owns the lifecycle of the dashboard's "Fetch Data" feature.
When the end user picks a set of symbols and clicks the control, the
backend calls :meth:`DownloadManager.start`, which discovers every live
expiry per symbol and spawns one :func:`nseoptions.worker.symbol_worker`
task per ``(symbol, expiry)`` pair, all sharing a single concurrency
semaphore. The manager aggregates per-worker progress so the frontend can
poll a single :class:`nseoptions.dashboard.schemas.FetchStatus`.

Persistence is intentionally decoupled: the manager passes a ``sink`` to
every worker, defaulting to a no-op recorder. The PostgreSQL writer is
wired into that seam later (``db.write_snapshot``) without any change to
this module - the deferred database integration only swaps the sink.

:NOTE: Expiry discovery and worker spawning run in a background bootstrap
    task so the HTTP request that triggers ``start`` returns immediately
    rather than blocking on the network. A single :class:`asyncio.Lock`
    serialises start/stop so overlapping requests cannot race.
"""

import asyncio
import datetime as dt

from nseoptions import worker
from nseoptions import NSEOptionChain

from nseoptions.dashboard import schemas
from nseoptions.dashboard.settings import AppSettings


class DownloadManager:
    """
    Lifecycle Controller for the In-Process Download Workers

    The manager starts, stops and reports on the pool of per-expiry
    download workers. It holds no option chain data itself - each worker
    streams its snapshots to the injected ``sink`` - and only tracks
    lightweight per-worker status for the dashboard controls panel.

    :type  settings: AppSettings
    :param settings: The immutable runtime settings; supplies the symbol
        universe, concurrency cap, poll interval and transport options.

    :type  sink: Callable or None
    :param sink: The async snapshot sink handed to every worker. When
        :obj:`None` a no-op recorder is used (the seam where the
        PostgreSQL writer is wired in once database integration lands).
    """

    def __init__(
        self, settings : AppSettings, sink : worker.Sink | None = None
    ) -> None:
        self._settings  = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrent)
        self._lock      = asyncio.Lock()

        # ? the persistence seam - defaults to the no-op recorder below
        self._sink = sink if sink is not None else self.__record__

        self._running    : bool = False
        self._symbols    : tuple = ()
        self._started_at : dt.datetime | None = None

        self._bootstrap : asyncio.Task | None = None
        self._tasks     : dict = {} # (symbol, expiry) -> asyncio.Task
        self._status    : dict = {} # (symbol, expiry) -> schemas.WorkerStatus


    @property
    def running(self) -> bool:
        """
        Whether a download session is currently active.

        :rtype:  bool
        :return: :obj:`True` between a successful ``start`` and the next
            ``stop`` (or server shutdown), otherwise :obj:`False`.
        """

        return self._running


    async def start(self, symbols : list | tuple | None = None) -> schemas.FetchStatus:
        """
        Start (or Restart) the Downloader for the Selected Symbols

        Any in-flight session is cancelled first, so calling ``start``
        with a new selection cleanly replaces the previous one. Expiry
        discovery and worker spawning happen in a background task, hence
        this coroutine returns a ``starting`` status without waiting on
        the network.

        :type  symbols: list or tuple or None
        :param symbols: The symbols to download. When empty or
            :obj:`None` the configured :attr:`AppSettings.symbols`
            universe is used.

        :rtype:  schemas.FetchStatus
        :return: The aggregate status immediately after the (re)start.
        """

        chosen = tuple(symbols) if symbols else tuple(self._settings.symbols)

        async with self._lock:
            await self.__cancel_all__()

            self._symbols    = chosen
            self._started_at = dt.datetime.now()
            self._running    = True

            self._bootstrap = asyncio.create_task(self.__bootstrap__(chosen))

        return self.status()


    async def stop(self) -> schemas.FetchStatus:
        """
        Cancel the Bootstrap and Every Running Worker

        :rtype:  schemas.FetchStatus
        :return: The aggregate status after everything has been stopped.
        """

        async with self._lock:
            await self.__cancel_all__()

        return self.status()


    def status(self) -> schemas.FetchStatus:
        """
        Snapshot the Aggregate Downloader Status

        :rtype:  schemas.FetchStatus
        :return: The live running flag, the selected symbols, the start
            time and the per-worker status list for the controls panel.
        """

        return schemas.FetchStatus(
            running    = self._running,
            symbols    = list(self._symbols),
            started_at = self._started_at.isoformat() if self._started_at else None,
            workers    = list(self._status.values())
        )


    async def __cancel_all__(self) -> None:
        """Cancel the bootstrap and all worker tasks and await them."""

        self._running = False

        pending : list = []
        if self._bootstrap is not None:
            self._bootstrap.cancel()
            pending.append(self._bootstrap)

        for task in self._tasks.values():
            task.cancel()
            pending.append(task)

        # ! await the cancellations so no orphan task survives a restart;
        # ! a blocking fetch already in a worker thread finishes harmlessly
        if pending:
            await asyncio.gather(*pending, return_exceptions = True)

        self._bootstrap = None
        self._tasks = {}
        self._status = {} # ! a stopped/restarted manager reports no workers


    async def __bootstrap__(self, symbols : tuple) -> None:
        """Discover live expiries per symbol and spawn one worker each."""

        for symbol in symbols:
            try:
                expiries = await asyncio.to_thread(self.__discover__, symbol)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.__set_error__(symbol, "(discovery)", str(exc))
                continue

            for expiry in expiries:
                key = (symbol, expiry)
                self._status[key] = schemas.WorkerStatus(
                    symbol = symbol, expiry = expiry, state = "starting"
                )
                self._tasks[key] = asyncio.create_task(worker.symbol_worker(
                    symbol, expiry, self._semaphore, self._sink,
                    verify = self._settings.verify,
                    timeout = self._settings.timeout,
                    interval = self._settings.interval,
                    nstrikes = self._settings.nstrikes,
                    waittime = self._settings.waittime,
                    on_status = self.__on_status__
                ))


    def __discover__(self, symbol : str) -> list:
        """Blocking expiry discovery for one symbol, run off the loop."""

        api = NSEOptionChain(
            symbol, verify = self._settings.verify, timeout = self._settings.timeout
        )

        return api.expiries() or []


    def __on_status__(self, symbol : str, expiry : str, **kwargs) -> None:
        """Fold a single worker status update into the registry."""

        status = self._status.get((symbol, expiry))
        if status is None:
            return

        state = kwargs.get("state")
        if state == "ok":
            status.state = "ok"
            status.detail = None

            timestamp = kwargs.get("timestamp")
            if timestamp is not None and timestamp != status.last_timestamp:
                status.snapshots += 1
                status.last_timestamp = timestamp
        elif state == "error":
            status.state = "error"
            status.detail = kwargs.get("detail")


    def __set_error__(self, symbol : str, expiry : str, detail : str) -> None:
        """Record a symbol-level (e.g. discovery) error in the registry."""

        self._status[(symbol, expiry)] = schemas.WorkerStatus(
            symbol = symbol, expiry = expiry, state = "error", detail = detail
        )


    async def __record__(self, symbol, expiry, response, model, opchain) -> None:
        """
        No-Op Persistence Sink - the PostgreSQL Writer Seam

        Database integration is deferred, so the default sink discards
        the snapshot. Per-worker progress is still tracked via the status
        hook, so the controls panel reflects live activity. Wiring the
        real writer here (``db.write_snapshot``) is the only change the
        deferred database phase needs.

        :rtype:  None
        :return: This sink intentionally returns nothing.
        """

        return None
