# -*- encoding: utf-8 -*-

"""
Asynchronous NSE Option Chain JSON Downloader

A standalone, :mod:`asyncio`-based service that concurrently polls the
NSE v3 option chain for a configurable set of index symbols and every
one of their live contract expiries, then archives each fresh snapshot
to a date-partitioned JSON file. It is the download-only precursor to
the planned ``cli.py`` and ``worker.py`` modules, merging their
orchestration and per-worker loop while deliberately excluding the
PostgreSQL writer and the option chain processing step (both of which
are integrated later, alongside the database project).

The only network primitive is the existing synchronous
:meth:`nseoptions.core.NSEOptionChain.response`, wrapped in
:func:`asyncio.to_thread` so that the proven retry and cookie re-warm
logic is reused verbatim without an ``aiohttp`` rewrite. A shared
:class:`asyncio.Semaphore` bounds the number of in-flight requests to
the NSE India website to avoid tripping its bot protection.

:NOTE: A snapshot is written only when the NSE market timestamp differs
    from the previously saved one for that ``(symbol, expiry)`` pair, so
    the on-disk archive holds one file per distinct market refresh. The
    expiry is part of the filename because the NSE v3 API returns the
    same ``records.timestamp`` for every expiry of a symbol in a single
    poll cycle, which would otherwise collide on disk.
"""

import os
import sys
import json
import asyncio
import logging
import warnings
import argparse

import datetime as dt

# ! append this script's directory so the local `nseoptions` package is
# importable when `download.py` is executed directly as a script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from nseoptions import NSEOptionChain

DEFAULT_SYMBOLS = ["NIFTY", "BANKNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "FINNIFTY"]

logger = logging.getLogger("nseoptions.download")


def buildparser() -> argparse.ArgumentParser:
    """
    Construct the Command-Line Argument Parser for the Downloader

    The parser exposes the runtime controls for the asynchronous
    download service. No database arguments are present since the
    PostgreSQL integration is intentionally out of scope for this
    module and is wired in later.

    :rtype:  argparse.ArgumentParser
    :return: A fully configured parser exposing the ``--symbols``,
        ``--interval``, ``--max-concurrent``, ``--no-verify`` and
        ``--output`` arguments.
    """

    parser = argparse.ArgumentParser(
        description = "Asynchronous NSE option chain JSON downloader."
    )

    parser.add_argument(
        "--symbols",
        nargs = "+",
        default = DEFAULT_SYMBOLS,
        help = "Index symbols to poll (defaults to the NSE indices)."
    )
    parser.add_argument(
        "--interval",
        type = int,
        default = 30,
        help = "Seconds to wait between two poll cycles per worker."
    )
    parser.add_argument(
        "--max-concurrent",
        dest = "max_concurrent",
        type = int,
        default = 3,
        help = "Maximum number of concurrent NSE fetches across workers."
    )
    parser.add_argument(
        "--no-verify",
        dest = "verify",
        action = "store_false",
        help = "Bypass SSL certificate verification (a warning is shown)."
    )
    parser.add_argument(
        "--output",
        default = "output",
        help = "Base output directory for the JSON snapshots."
    )

    return parser


def enablesslbypass() -> None:
    """
    Disable SSL Verification Warnings for ``--no-verify`` Runs

    Mirrors the behaviour of :mod:`main`: a single :class:`UserWarning`
    is surfaced to the operator and the otherwise per-request
    ``urllib3`` insecure-request warnings are silenced so the service
    log stays readable across many concurrent workers.

    :NOTE: ``urllib3`` is imported lazily here because it is only needed
        when SSL verification is bypassed.
    """

    import urllib3 # noqa: E402 # only needed when verification is bypassed

    warnings.warn(
        "SSL certificate verification is DISABLED via `--no-verify`.",
        stacklevel = 2
    )
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def sanitizetimestamp(timestamp : str) -> str:
    """
    Make an NSE Market Timestamp Safe for Use in a Filename

    The NSE market timestamp (example ``13-Jun-2026 12:33:49``) carries
    a colon and a space, neither of which is safe across file systems.
    The colons are stripped and the space is replaced with an
    underscore, yielding ``13-Jun-2026_123349``.

    :type  timestamp: str
    :param timestamp: The raw ``records.timestamp`` value as reported by
        the NSE v3 option chain payload.

    :rtype:  str
    :return: A filesystem-safe rendering of the timestamp.
    """

    return timestamp.replace(":", "").replace(" ", "_")


def buildfilepath(
    outdir : str, fetchdate : str, timestamp : str, symbol : str, expiry : str
) -> str:
    """
    Assemble the Output File Path for a Single Snapshot

    The layout is ``<outdir>/<fetchdate>/<timestamp>-<symbol>-<expiry>``
    with a ``.json`` suffix. The expiry is part of the filename because
    a single poll cycle returns the same market timestamp for every
    expiry of a symbol, which would otherwise overwrite on disk.

    :type  outdir: str
    :param outdir: Base output directory (resolved against the current
        working directory, matching :mod:`main`).

    :type  fetchdate: str
    :param fetchdate: The fetch-date partition, formatted ``%Y-%m-%d``.

    :type  timestamp: str
    :param timestamp: The raw NSE market timestamp; it is sanitized via
        :func:`sanitizetimestamp` before being placed in the filename.

    :type  symbol: str
    :param symbol: The traded symbol, example ``NIFTY``.

    :type  expiry: str
    :param expiry: The contract expiry in ``%d-%b-%Y`` form, example
        ``16-Jun-2026``.

    :rtype:  str
    :return: The path of the JSON file to write.
    """

    filename = f"{sanitizetimestamp(timestamp)}-{symbol}-{expiry}.json"
    return os.path.join(outdir, fetchdate, filename)


def writesnapshot(response : dict, filepath : str) -> None:
    """
    Persist a Raw Option Chain Payload to a JSON File

    The parent directory is created on demand and the payload is written
    with the same formatting as :func:`main.writejson` (two-space
    indent, insertion order preserved, non-serialisable values coerced
    via ``str``). The function is synchronous and is intended to be
    invoked through :func:`asyncio.to_thread` so it never blocks the
    event loop.

    :type  response: dict
    :param response: The raw v3 option chain payload returned by
        :meth:`nseoptions.core.NSEOptionChain.response`.

    :type  filepath: str
    :param filepath: Destination path produced by :func:`buildfilepath`.
    """

    os.makedirs(os.path.dirname(filepath), exist_ok = True)

    with open(filepath, "w") as f:
        json.dump(response, f, indent = 2, sort_keys = False, default = str)


async def discoverexpiries(symbol : str, verify : bool) -> list:
    """
    Discover the Live Contract Expiries for a Single Symbol

    A throwaway :class:`nseoptions.core.NSEOptionChain` instance is
    configured and its blocking :meth:`expiries` call is dispatched to a
    worker thread via :func:`asyncio.to_thread`. A ``None`` result (the
    discovery falling through its internal retry loop) is normalised to
    an empty list so the orchestrator can skip the symbol cleanly.

    :type  symbol: str
    :param symbol: The index symbol whose expiries are to be discovered.

    :type  verify: bool
    :param verify: Whether to verify SSL certificates on the request.

    :rtype:  list
    :return: The list of expiry strings (``%d-%b-%Y``), or an empty list
        when none could be discovered.
    """

    api = NSEOptionChain(symbol, verify = verify)
    api.setconfig()

    expiries = await asyncio.to_thread(api.expiries)

    # ! `expiries()` can fall through its retry loop and return None
    expiries = expiries or []
    logger.info("%s : discovered %d expiries", symbol, len(expiries))

    return expiries


async def symbol_worker(
    symbol : str,
    expiry : str,
    semaphore : asyncio.Semaphore,
    verify : bool,
    interval : int,
    outdir : str
) -> None:
    """
    Poll a Single ``(symbol, expiry)`` Pair Until Cancelled

    The worker owns a dedicated :class:`nseoptions.core.NSEOptionChain`
    instance (and therefore its own warmed session) so that concurrent
    workers never share mutable request state. On every cycle it
    acquires the shared semaphore, fetches the chain in a worker thread,
    and writes a snapshot only when the market timestamp has advanced
    since the last write. Transient :class:`ValueError` and
    :class:`ConnectionError` failures are logged and retried on the next
    cycle, while :class:`asyncio.CancelledError` is allowed to propagate
    for a graceful shutdown.

    :type  symbol: str
    :param symbol: The traded symbol to poll, example ``NIFTY``.

    :type  expiry: str
    :param expiry: The contract expiry in ``%d-%b-%Y`` form.

    :type  semaphore: asyncio.Semaphore
    :param semaphore: Shared concurrency guard bounding the number of
        simultaneous NSE fetches across all workers.

    :type  verify: bool
    :param verify: Whether to verify SSL certificates on each request.

    :type  interval: int
    :param interval: Seconds to wait between two consecutive poll cycles.

    :type  outdir: str
    :param outdir: Base output directory for the JSON snapshots.
    """

    api = NSEOptionChain(symbol, verify = verify)
    api.setconfig()
    api.setexpiry(expiry)

    last_timestamp = None
    while True:
        try:
            async with semaphore:
                response = await asyncio.to_thread(api.response, 20)

            timestamp = response["records"]["timestamp"]
            if timestamp != last_timestamp:
                # ! recompute the date every cycle so a service running
                # past midnight rolls over into the new day's directory
                fetchdate = dt.datetime.now().strftime("%Y-%m-%d")
                filepath = buildfilepath(
                    outdir, fetchdate, timestamp, symbol, expiry
                )
                await asyncio.to_thread(writesnapshot, response, filepath)

                last_timestamp = timestamp
                logger.info("[%s/%s] saved %s", symbol, expiry, filepath)
            else:
                logger.debug(
                    "[%s/%s] unchanged at %s, skipped",
                    symbol, expiry, timestamp
                )
        except (ValueError, ConnectionError) as err:
            logger.error("[%s/%s] fetch failed - %s", symbol, expiry, err)

        await asyncio.sleep(interval)


async def run_service(
    symbols : list,
    interval : int,
    max_concurrent : int,
    verify : bool,
    outdir : str
) -> None:
    """
    Orchestrate Concurrent Download Workers for All Symbols

    Expiries are discovered for every symbol concurrently (a single
    symbol's failure does not abort the others), one worker task is
    spawned per ``(symbol, expiry)`` pair, and all workers are then run
    under a shared :class:`asyncio.Semaphore`. On cancellation every
    worker is cancelled and awaited so the service shuts down cleanly.

    :type  symbols: list
    :param symbols: Index symbols to poll.

    :type  interval: int
    :param interval: Seconds between poll cycles, forwarded to workers.

    :type  max_concurrent: int
    :param max_concurrent: Upper bound on simultaneous NSE fetches.

    :type  verify: bool
    :param verify: Whether to verify SSL certificates on each request.

    :type  outdir: str
    :param outdir: Base output directory for the JSON snapshots.
    """

    semaphore = asyncio.Semaphore(max_concurrent)

    discovered = await asyncio.gather(
        *[discoverexpiries(symbol, verify) for symbol in symbols],
        return_exceptions = True
    )

    tasks = []
    active = 0
    for symbol, expiries in zip(symbols, discovered):
        if isinstance(expiries, Exception):
            logger.error(
                "%s : expiry discovery failed - %s", symbol, expiries
            )
            continue

        if not expiries:
            logger.warning("%s : no expiries discovered, skipping", symbol)
            continue

        active += 1
        for expiry in expiries:
            tasks.append(
                asyncio.create_task(
                    symbol_worker(
                        symbol, expiry, semaphore, verify, interval, outdir
                    )
                )
            )

    if not tasks:
        logger.error(
            "no workers to run - every symbol failed or had no expiries"
        )
        return

    logger.info("started %d workers across %d symbols", len(tasks), active)

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        # ! propagate cancellation to every worker, then await teardown
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions = True)
        raise


def main() -> None:
    """
    Command-Line Entry Point for the Async Download Service

    Parses the runtime arguments, optionally enables the SSL bypass, and
    runs the asynchronous service until interrupted. A keyboard interrupt
    (CTRL + C) is caught so the process exits cleanly with status zero.
    """

    logging.basicConfig(
        level = logging.INFO,
        format = "%(asctime)s : %(levelname)s : %(message)s"
    )

    args = buildparser().parse_args()

    if not args.verify:
        enablesslbypass()

    try:
        asyncio.run(
            run_service(
                args.symbols,
                args.interval,
                args.max_concurrent,
                args.verify,
                args.output
            )
        )
    except KeyboardInterrupt:
        logger.info("stopped by user (CTRL + C), exiting gracefully")
        sys.exit(0)


if __name__ == "__main__":
    main()
