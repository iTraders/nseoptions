# -*- encoding: utf-8 -*-

"""
SQLite-Backed Per-Strike History Store

Persists a per-strike, per-leg time series (LTP / OI / change-in-OI / IV /
volume) for every poll tick so the dashboard can chart how an individual
strike evolved through the session - and survive a server restart.

The store is intentionally simple and dependency-free (stdlib ``sqlite3``).
Writes happen only from the single poller, reads from the request handlers;
a process-wide lock plus WAL journaling keep the single connection safe
across the thread-pool, and an ``INSERT OR IGNORE`` on a uniqueness key
makes duplicate ticks (NSE repeats a timestamp within the interval)
idempotent.

@author:  Debmalya Pramanik
@version: v0.0.1
@copywright: 2024; Debmalya Pramanik
"""

import os        # filesystem paths + ensuring the history directory exists
import sqlite3   # the embedded, dependency-free time-series backend
import threading # serialize the single connection across the thread-pool

from nseoptions.dashboard import schemas

# ! allow-listed series columns -> guards the dynamic column interpolation
# ! in :meth:`HistoryStore.series` against any sql injection on `field`
SERIES_FIELDS = {"ltp", "oi", "chg_oi", "iv", "volume"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS option_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol     TEXT NOT NULL,
    expiry     TEXT NOT NULL,
    strike     REAL NOT NULL,
    leg        TEXT NOT NULL,
    ts         TEXT NOT NULL,
    ltp        REAL,
    oi         REAL,
    chg_oi     REAL,
    iv         REAL,
    volume     REAL,
    underlying REAL,
    UNIQUE(symbol, expiry, strike, leg, ts)
);

CREATE INDEX IF NOT EXISTS ix_history_lookup
    ON option_history (symbol, expiry, strike, leg, ts);

CREATE TABLE IF NOT EXISTS snapshot_meta (
    symbol    TEXT NOT NULL,
    expiry    TEXT NOT NULL,
    ts        TEXT NOT NULL,
    pcr       REAL,
    max_pain  REAL,
    tot_oi_ce REAL,
    tot_oi_pe REAL,
    atm       REAL,
    PRIMARY KEY (symbol, expiry, ts)
);
"""


class HistoryStore:
    """
    A Durable, Per-Strike Option History Store

    :type  path: str
    :param path: The sqlite file path. The parent directory is created if
        it does not already exist.

    :type  symbol: str
    :param symbol: The symbol whose history this store records. Normalized
        to upper case and stamped onto every row.
    """

    def __init__(self, path : str, symbol : str) -> None:
        self.symbol = symbol.upper()

        os.makedirs(os.path.dirname(path), exist_ok = True)

        # ! check_same_thread=False + an explicit lock so the poll loop and
        # ! the (thread-pooled) read handlers can share one connection
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread = False)

        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()


    def write(self, chain : schemas.ChainOut) -> int:
        """
        Persist one option chain snapshot as per-strike-leg rows.

        :type  chain: schemas.ChainOut
        :param chain: The processed snapshot to record. Each strike emits
            up to two rows (CE and PE) keyed on the snapshot timestamp.

        :rtype: int
        :return: The number of strike-leg rows offered to the store (the
            insert is idempotent, so existing ticks are silently ignored).
        """

        timestamp = chain.timestamp
        rows = []

        for row in chain.rows:
            for leg, quote in (("CE", row.ce), ("PE", row.pe)):
                if quote is None:
                    continue

                rows.append((
                    self.symbol, chain.expiry, row.strikePrice, leg, timestamp,
                    quote.lastPrice, quote.openInterest, quote.changeinOpenInterest,
                    quote.impliedVolatility, quote.totalTradedVolume, chain.underlying
                ))

        if not rows:
            return 0

        with self._lock:
            self._conn.executemany(
                "INSERT OR IGNORE INTO option_history "
                "(symbol, expiry, strike, leg, ts, ltp, oi, chg_oi, iv, volume, underlying) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO snapshot_meta "
                "(symbol, expiry, ts, pcr, max_pain, tot_oi_ce, tot_oi_pe, atm) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.symbol, chain.expiry, timestamp, chain.put_call_ratio,
                    None, chain.tot_oi_ce, chain.tot_oi_pe, chain.atm
                )
            )
            self._conn.commit()

        return len(rows)


    def series(
        self,
        expiry : str,
        strike : float,
        leg    : str,
        field  : str = "ltp",
        since  : str | None = None
    ) -> schemas.HistoryOut:
        """
        Return the time series of one ``field`` for a strike-leg.

        :type  field: str
        :param field: One of :data:`SERIES_FIELDS` (``ltp``/``oi``/``chg_oi``/
            ``iv``/``volume``). An unknown field falls back to ``ltp``.

        :type  since: str or None
        :param since: Optional inclusive lower bound on the timestamp.
        """

        column = field if field in SERIES_FIELDS else "ltp"

        query  = (
            f"SELECT ts, {column} FROM option_history "
            "WHERE symbol = ? AND expiry = ? AND strike = ? AND leg = ?"
        )
        params : list = [self.symbol, expiry, float(strike), leg.upper()]

        if since:
            query += " AND ts >= ?"
            params.append(since)

        query += " ORDER BY ts ASC"

        with self._lock:
            cursor = self._conn.execute(query, params)
            records = cursor.fetchall()

        points = [
            schemas.HistoryPoint(ts = ts, value = float(value if value is not None else 0.0))
            for ts, value in records
        ]

        return schemas.HistoryOut(
            symbol = self.symbol, expiry = expiry, strike = float(strike),
            leg = leg.upper(), field = column, points = points
        )


    def close(self) -> None:
        """Close the underlying sqlite connection."""

        with self._lock:
            self._conn.close()
