# NSE Options — Production ReactJS Dashboard

> Approved implementation plan. Tracks the architecture, decisions, and phased build of a
> production-grade ReactJS dashboard served by a FastAPI backend, launched via `python dashboard.py`.
>
> **..versionchanged:: 2026-06-13** — re-architected onto **PostgreSQL** (no local SQLite) and a
> user-driven **"Fetch Data"** trigger that starts the asynchronous downloader. See *Context*.

## Context
`nseoptions` fetches & cleans NSE India option-chain data. `master` is now fully migrated to the
**NSE Option Chain v3 API**, and a sibling branch (`feature/asynchronous-download`) defines an
**asynchronous, multi-symbol downloader** that writes option-chain snapshots to **PostgreSQL**.
This project delivers a modern, **production-grade ReactJS dashboard** (served by a Python backend)
that **reads everything from that PostgreSQL database** and lets the user start the downloader from
the UI. It delivers four analytical capabilities:

1. **Live option chain** — Sensibull-style heatmap table mirroring the Excel layout.
2. **Historic price tracking** — per-strike time series of LTP / OI / IV across a session.
3. **Strategy builder** — multi-leg payoff / greeks / breakeven analyzer.
4. **Auto-suggest** — analyze the current scenario (PCR, max-pain, OI buildup, IV) and recommend strategies.

**Why this revision (the two required changes):**
1. **No local SQLite.** All dashboard content is read from **PostgreSQL**; nothing is persisted to a
   local SQLite file. History is *derived from the snapshot series* in PostgreSQL.
2. **A "Fetch Data" button.** The user boots the dashboard, selects symbols/indexes, and clicks
   *Fetch Data* to **start the asynchronous download** of all selected symbols (continuous, with a
   **Stop** toggle). The dashboard then renders from the snapshots the downloader writes to PostgreSQL.

**Hard constraint:** `nseoptions/core.py` and `nseoptions/processing.py` are the locked, v3-migrated
data module — **do not modify them**. We only consume their public API and add NEW files. The
PostgreSQL writer/reader and the async downloader are **new** files; the bespoke NSE poller that the
earlier dashboard prototype owned is **removed** (the reused async worker drives all NSE traffic).

## Upstream state this plan builds on
- **v3 migration (`master`):** expiry is now **required** — call `setexpiry()` after `setconfig()`;
  `expiries()` discovers valid contracts; `core.py` warms its own Akamai session
  (`__newsession__`), so the dashboard's old cookie-priming workaround is **no longer needed**.
- **v3 leg-field rename (load-bearing):** `makeclean()`'s last 4 leg columns changed
  `bidQty,bidprice,askQty,askPrice` → **`buyQuantity1,buyPrice1,sellQuantity1,sellPrice1`**
  (the first 10 of the 14 leg fields are unchanged; 29-col invariant preserved).
- **Async downloader (`feature/asynchronous-download`, design only):** `cli.py`/`worker.py` fetch all
  index symbols × live expiries concurrently and call `db.write_snapshot(...)`; the writer was a
  stub and the **PostgreSQL schema was deferred**. **This plan now owns that schema** via a shared
  `nseoptions/db` module used by *both* the downloader and the dashboard.

## Locked decisions
- **Interpreter:** Python **3.13** (Anaconda); module uses `X | Y` union syntax (needs ≥3.10).
- **Source of truth:** **PostgreSQL** (single source of truth). The dashboard is a **reader**; the
  reused async **worker** is the only writer. *(No local SQLite.)*
- **DB ownership:** a **shared `nseoptions/db` module** owns the DDL, connection pool, the real
  `write_snapshot` (replacing the async stub) and the dashboard read queries.
- **Fetch trigger:** **in-process orchestration** — the FastAPI backend imports the async worker
  machinery and starts/cancels download workers as `asyncio` tasks in its own event loop.
- **Fetch scope:** **continuous + Stop toggle** — click starts the looping, timestamp-deduped
  downloader for the selected symbols; a Stop halts it cleanly.
- **Frontend:** Vite + React + TypeScript + TailwindCSS + shadcn/ui. Industry-grade, reusable components.
- **Backend:** FastAPI + Uvicorn + **asyncpg** (async PG pool); native async WebSocket fan-out;
  pydantic = typed contract; `StaticFiles` SPA mount; `asyncio.to_thread` for any blocking work.
  Greeks via `math.erf` — **no scipy**.
- **Live layer:** PostgreSQL-fed — a single backend **DB tail-poll** advances on a new
  `nse_timestamp` and fans the snapshot out to subscribed WS clients (works whether the downloader
  runs in-process or as a standalone `nseoptions` CLI). *(Optional later: asyncpg `LISTEN/NOTIFY`.)*
- **Auto-suggest (IV):** deterministic **rules-based** engine behind a pluggable `SuggestionProvider`
  ABC so a `ClaudeSuggester` can slot in later with zero changes to `service.py`/`server.py`.
- **Launch:** root-level `dashboard.py` via `python dashboard.py` (argparse, incl. PostgreSQL args).
- **Python style:** match the repo exactly (see below).

## Development guidelines (follow on every implementation step)
- **`/python-code-format` skill is mandatory** for every new/edited Python file
  (`nseoptions/db/*`, `worker.py`, `cli.py`, `downloader.py`, the dashboard modules). **Always read
  the whole file before writing or editing.**
- **Deploy the Python coding agents from the global configuration directory** to write/modify
  Python; they enforce the project's formatting standards.
- **Detailed, atomic git commit after every important step / file change** (gitmoji messages,
  per the checklist below), so the work is graceful to track and cherry-pick. Include a
  `Co-Authored-By` footer.

## Python style to match (studied in core.py / processing.py / main.py)
`# -*- encoding: utf-8 -*-` header · module docstring then `@author`/`@version`/`@copywright` ·
**spaces around `=` in kwargs** (`header = False`) · **spaces around `:` in annotations** (`response : dict`) ·
`# ?` and `# !` inline markers · grouped imports with trailing comments · full type hints ·
`dt` alias for datetime · staticmethods where pure · `..versionchanged::` annotations · gitmoji commits.

## Data contract (frozen — consume, never re-derive)
- `nseoptions.NSEOptionChain(symbol, verify=False)` → `.setconfig(type="index")`; **`.expiries()`** lists
  valid contracts; **`.setexpiry(expiry)`** rebuilds the v3 URI; `.response(waittime)` → raw NSE JSON
  for that one expiry. *(Expiry is required in v3.)*
- Raw JSON: `records.{timestamp, underlyingValue, expiryDates[], data[].{strikePrice, expiryDate, CE{...}, PE{...}}}`,
  `filtered.{CE,PE}.{totOI,totVol}`.
- `nseoptions.processing.OptionChainProcessing(symbol, apikey, response, expiry, nstrikes=20)`:
  `.makeclean()` → **29-col** DataFrame (14 CE | `strikePrice` | 14 PE **mirrored**) and sets attrs
  `underlying, timestamp, put_call_ratio, tot_oi_ce/pe, tot_vol_ce/pe, atm, lstrike, hstrike`;
  `imultiple()` is a **staticmethod**.
- **v3 per-leg fields (14):** openInterest, changeinOpenInterest, pchangeinOpenInterest,
  totalTradedVolume, impliedVolatility, lastPrice, change, pChange, totalBuyQuantity,
  totalSellQuantity, **buyQuantity1, buyPrice1, sellQuantity1, sellPrice1**.
- **No greeks exist** → compute via Black-Scholes from IV. Analytics use the **raw full
  `records.data[]`** (all strikes, both legs) while the table/PCR/totals reuse the `opchain_rows` +
  snapshot metrics stored by the writer.
- `imultiple`: NIFTY 50, BANKNIFTY 100, MIDCPNIFTY 25, NIFTYNXT50 100, else 50.

### Snapshot writer contract (shared `nseoptions/db`)
One row per `(symbol, expiry, nse_timestamp)` written by `write_snapshot(pool, symbol, expiry,
response, model, opchain)`:
`symbol, expiry(DATE), nse_timestamp, fetched_at, underlying, atm, multiple, tot_oi_ce/pe,
tot_vol_ce/pe, put_call_ratio, raw_response(JSONB full payload), opchain_rows(JSONB =
opchain.to_dict("records"))`. Application-layer dedup (worker compares `records.timestamp`) +
DB-layer `UNIQUE(symbol, expiry, nse_timestamp)` safety net (`INSERT ... ON CONFLICT DO NOTHING`).
*(`atm`/`multiple` are added beyond the original async contract because the dashboard needs the ATM
highlight and strike multiple.)*

## Design tokens (from `template/NSE Option Chain.xlsx`)
- Heatmap 3-stop (on %chng-in-OI / OI intensity): Red `#F8696B` → Yellow `#FFEB84` → Green `#63BE7B`.
- Layout: CALL block (OI/IV/LTP/VOLUME/CHNG/QTY/BID/ASK) left · STRIKE center · PUT block mirrored
  right; ATM row highlighted; sticky header + sticky strike column.
- Sensibull-style extras beyond Excel: Max-Pain bar, Support/Resistance OI walls, PCR gauge, IV smile.

## Architecture
```
nseoptions/
  db/               # NEW shared layer (used by BOTH downloader + dashboard)
    __init__.py     # re-exports create_pool/init_schema/write_snapshot/reader fns
    schema.sql      # option_snapshot DDL (+ atm/multiple), UNIQUE + index
    pool.py         # create_pool(...), init_schema(pool)  [idempotent CREATE IF NOT EXISTS]
    writer.py       # write_snapshot(...) real impl (ON CONFLICT DO NOTHING)
    reader.py       # latest_snapshot, available_symbols, expiries_for, series, latest_per
  cli.py            # async downloader entrypoint (per async plan) → uses nseoptions.db
  worker.py         # symbol_worker(...) per (symbol, expiry) loop → write_snapshot
  dashboard/
    __init__.py     # launch(symbol, symbols, expiry, host, port, verify, interval, nstrikes,
                    #        max_concurrent, pg_host/port/database/user/password, dev)
    settings.py     # frozen AppSettings: pg_* (or database_url), symbols, max_concurrent, view defaults
    server.py       # create_app(settings): pool lifespan + init_schema, read-service + DownloadManager,
                    #   REST+WS routes (incl. /api/symbols + /api/fetch/{start,stop,status}), SPA mount LAST
    service.py      # SnapshotService: PG reader → ChainOut/meta builders, WS fan-out via DB tail-poll
    downloader.py   # NEW DownloadManager: start(symbols)/stop()/status() over worker tasks + semaphore
    analytics.py    # UNCHANGED: max_pain, oi_walls, black_scholes_greeks (erf), payoff_curve, iv_smile
    suggester.py    # UNCHANGED: SuggestionProvider ABC + RulesBasedSuggester
    schemas.py      # pydantic v2 models = REST/WS contract (v3 leg fields + fetch-control models)
    frontend/       # Vite+React+TS+Tailwind+shadcn; build → frontend/dist served by server.py
  # (history.py is DELETED — superseded by PostgreSQL)
dashboard.py        # root launcher, argparse incl. PostgreSQL connection args
requirements-dashboard.txt   # fastapi, uvicorn[standard], pydantic>=2, asyncpg>=0.29
tests/              # offline fixtures + pytest; frontend vitest/RTL
```

### Backend service (the key pieces)
- **No bespoke poller.** The dashboard does **not** fetch NSE or cache it as truth. The reused async
  **`worker.symbol_worker`** is the only NSE→PostgreSQL writer.
- **`SnapshotService` (reader):** builds `ChainOut`/`MetaOut` from the **latest DB snapshot** for a
  `(symbol, expiry)` — assembles `StrikeRow`s from the stored `opchain_rows` (reusing the existing
  `_num`/`_leg_quote`/`StrikeRow` helpers) plus the snapshot metrics. Analytics/payoff/suggestions
  read the stored `raw_response` JSONB and call the **unchanged** `analytics.*` / `suggester.*`.
- **`DownloadManager` (control):** `start(symbols)` → off-loop `expiries()` per symbol, spawns one
  `asyncio.Task` per `(symbol, expiry)` over a shared `asyncio.Semaphore(max_concurrent)` + shared
  pool; `stop()` cancels all; `status()` reports running/symbols/started_at/last-writes/errors.
  Idempotent restart on a new selection.
- **WS live layer:** one background **DB tail-poll** checks the latest `nse_timestamp` per active
  `(symbol, expiry)` subscription and broadcasts the freshly-built snapshot when it advances. New
  clients get the current snapshot immediately. All pandas/DB work via `asyncio.to_thread`/asyncpg.

### Endpoints
REST (`/api`): `health` (DB + download status), `symbols` (selectable + availability),
`meta?symbol=`, `chain?symbol=&expiry=`, `history?symbol=&expiry=&strike=&leg=&field=`,
`analytics?symbol=&expiry=`, `POST strategy/payoff` (body carries `symbol`), `suggestions?symbol=&expiry=`,
**`POST fetch/start` (`{symbols:[…]}`)**, **`POST fetch/stop`**, **`GET fetch/status`**.
WS `/ws?symbol=&expiry=`: on connect `{type:snapshot}`; per new timestamp `{type:tick}`;
`{type:status}`; client `{type:subscribe,symbol,expiry}`. Heartbeat + client backoff reconnect.
Pydantic: `LegQuote, StrikeRow, Greeks, ChainOut, MetaOut, HealthOut, SymbolInfo, SymbolsOut,
FetchRequest, FetchStatus, AnalyticsOut, StrategyLeg, PayoffIn/Out, Suggestion, SuggestionsOut`.

### PostgreSQL schema (`nseoptions/db/schema.sql`)
```sql
CREATE TABLE IF NOT EXISTS option_snapshot (
    id             BIGSERIAL PRIMARY KEY,
    symbol         VARCHAR(50)  NOT NULL,
    expiry         DATE         NOT NULL,
    nse_timestamp  TIMESTAMP    NOT NULL,
    fetched_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    underlying     NUMERIC(14,4),
    atm            NUMERIC(14,4),
    multiple       INTEGER,
    tot_oi_ce      BIGINT,  tot_oi_pe  BIGINT,
    tot_vol_ce     BIGINT,  tot_vol_pe BIGINT,
    put_call_ratio NUMERIC(10,4),
    raw_response   JSONB        NOT NULL,
    opchain_rows   JSONB        NOT NULL,
    UNIQUE (symbol, expiry, nse_timestamp)
);
CREATE INDEX IF NOT EXISTS ix_snapshot_lookup
    ON option_snapshot (symbol, expiry, nse_timestamp DESC);
```
**History is derived, not stored separately:** `reader.series(...)` expands `opchain_rows`
(`jsonb_array_elements`) across the snapshot series for a `(symbol, expiry, strike, leg)` ordered by
`nse_timestamp`. *(A normalized per-strike table is a possible future optimization, not needed now.)*

### Algorithms (analytics.py — unchanged)
- **Black-Scholes** (`σ=iv/100`, `r=0.065`, `t=max((expiry@15:30IST−now)/yr, 1e-6)`, `Φ` via
  `math.erf`): price/delta/gamma/theta(per-day)/vega(per-1%)/rho. Missing/zero IV → intrinsic-sign
  delta, others 0 + `iv_missing` flag; `t→0` → intrinsic, gamma/vega 0.
- **Payoff**: grid 0.9·minK→1.1·maxK (200 pts); per-leg intrinsic minus premium; breakevens =
  sign-change interpolation; unbounded tails → `None`; net greeks summed at spot.
- **Max-pain**: `argmin_E Σ CE_OI·max(E−K,0)+PE_OI·max(K−E,0)`; empty OI → `no_data`.
- **OI walls**: resistance = top CE-OI strikes ≥ ATM; support = top PE-OI strikes ≤ ATM.
- **Rules suggester**: `MarketContext{pcr, atm_iv, iv_regime, trend, dte, maxpain-gap}` → decision
  table → each run through `payoff_curve`; `rationale[]`; sorted by `score`.

### Frontend (`frontend/src`)
- `lib/`: `api.ts` (typed fetch, zod-validated, base from `VITE_API_BASE`), `ws.ts` (reconnect/backoff),
  `heatmap.ts`, `format.ts`, `greeks.ts`.
- `store/dashboard.ts` (**Zustand** UI-only: active `symbol`, `selectedSymbols`, expiry,
  selectedStrike, builderLegs, heatmapMetric, **download state**, theme). Server state in
  **TanStack Query**; `useChainSocket` writes WS ticks into the query cache.
- **New controls:** `SymbolSelector` (multi-select of indices), `FetchDataButton` (start/stop toggle
  + spinner/status), `DownloadStatus` badge, and a **standby/empty state** when the DB has no data
  for the selection yet ("Select symbols → Fetch Data").
- **New hooks:** `useSymbols`, `useFetchControl` (start/stop + poll `fetch/status`); existing hooks
  (`useChain/useMeta/useHistory/useAnalytics/usePayoff/useSuggestions/useChainSocket`) gain a
  `symbol` argument and read the PostgreSQL-backed endpoints.
- **Unchanged components:** **OptionChainTable** (mirrored CALL|STRIKE|PUT, virtualized, sticky),
  **HeatCell**, **PCRGauge, MaxPainChart, OIWallBar, IVSmileChart, KpiStat, StrikeHistoryChart,
  StrategyLegEditor, PayoffChart, PayoffSummary, GreeksPanel, SuggestionCard/List**.
- Pages/tabs: Chain · History · Builder · Suggestions. Theme via Tailwind config + CSS vars.
- **Serving:** `vite build` → `frontend/dist`; `server.py` mounts it `html=True` after `/api`+`/ws`.
  Dev (`--dev`): Vite `:5173` + CORS to `:8000`; prod single-origin (no CORS).

### Root launcher `dashboard.py`
argparse `--symbol`(initial view) `--symbols`(downloadable set, default 5 indices) `--expiry`
`--host --port --interval --nstrikes --max-concurrent` `--pg-host --pg-port --pg-database --pg-user
--pg-password`(or `DATABASE_URL` env) `--no-verify(dest=verify)` `--dev`; `sys.path.append` like
main.py; calls `nseoptions.dashboard.launch(...)` which builds settings and `uvicorn.run`s.

## Phased plan (commit after each; gitmoji; `/python-code-format` + global Python agents)
> Implementation is **gradual**. Items are unchecked; tick them as completed.

### Phase A — shared PostgreSQL layer (foundation, no deps)
- [ ] **A1** `nseoptions/db/{schema.sql,pool.py,__init__.py}` — `option_snapshot` DDL + `create_pool`/`init_schema`. → `✨ add shared postgres db package (pool + schema)`
- [ ] **A2** `db/writer.py` real `write_snapshot` (ON CONFLICT dedup, stores atm/multiple). → `✨ implement postgres snapshot writer`
- [ ] **A3** `db/reader.py` (`latest_snapshot`, `available_symbols`, `expiries_for`, `series`, `latest_per`). → `✨ add postgres read queries for the dashboard`
- [ ] **A4** add `asyncpg>=0.29` to `requirements-dashboard.txt` (+ `pyproject.toml` if aligning with async). → `🤖 declare asyncpg dependency`

### Phase B — async downloader bound to the real DB *(integrate async branch, or build here)*
- [ ] **B1** `cli.py`/`worker.py` present & importing shared `db`; worker computes `atm`/`multiple` and calls the **real** `write_snapshot`. → `✨ wire async worker to the real postgres writer`

### Phase C — dashboard backend → PostgreSQL reader + DownloadManager
- [ ] **C1** `settings.py`: drop `db_path`; add pg_* (or `database_url`), `symbols`, `max_concurrent`; `symbol`/`expiry` become view defaults. → `♻️ settings: postgres connection + symbol selection`
- [ ] **C2** `downloader.py`: `DownloadManager` (start/stop/status over worker tasks + semaphore + pool). → `✨ add in-process download manager (fetch-data control)`
- [ ] **C3** `service.py`: remove poller/cookie-priming/SQLite hooks; build chain/meta from DB; WS via DB tail-poll. → `♻️ service: read snapshots from postgres, drop the bespoke poller`
- [ ] **C4** `schemas.py`: v3 leg fields + `SymbolsOut`/`FetchRequest`/`FetchStatus` + `symbol` on `PayoffIn` + freshness flags. → `♻️ schemas: v3 leg fields + fetch-control contract`
- [ ] **C5** `server.py`: pool lifespan + `init_schema`; read-service + `DownloadManager`; `/api/symbols` + `/api/fetch/{start,stop,status}`; `symbol` param on routes; WS symbol+expiry; remove `HistoryStore`. → `♻️ server: postgres-backed routes + fetch-data endpoints`
- [ ] **C6** delete `history.py`. → `🔥 remove sqlite history store (superseded by postgres)`
- [ ] **C7** `dashboard.py` + `__init__.launch`: DB args + `--symbols` + `--max-concurrent`. → `♻️ launcher: postgres + downloader controls`

### Phase D — frontend → multi-symbol + Fetch Data
- [ ] **D1** `types/contract.ts`: v3 leg fields + fetch/symbol types. → `♻️ frontend contract: v3 leg fields + fetch types`
- [ ] **D2** store symbol/download state + `useSymbols`/`useFetchControl`; add `symbol` to existing hooks. → `✨ frontend: symbol selection + fetch-control hooks`
- [ ] **D3** `SymbolSelector` + `FetchDataButton` (start/stop + status) + `DownloadStatus` + standby/empty state. → `✨ frontend: symbol selector + fetch-data button`
- [ ] **D4** wire panels to symbol-scoped, postgres-backed data; WS with symbol. → `♻️ frontend: scope panels to selected symbol`

### Phase E — tests, docs, polish
- [ ] **E1** backend tests: writer upsert/dedup, reader `ChainOut` + history series, `DownloadManager` start/stop (fixtures + fake/integration pool). → `✅ backend tests for postgres writer/reader + manager`
- [ ] **E2** frontend tests: `SymbolSelector`/`FetchDataButton` states, MSW fetch endpoints; `HeatCell` snapshot unchanged. → `✅ frontend tests for fetch-data controls`
- [ ] **E3** README dashboard section (postgres setup, fetch flow) + mark plan statuses. → `📝 document the postgres-backed dashboard + fetch flow`

## Verification
- Local PostgreSQL up; `python dashboard.py --pg-host localhost --pg-database nseoptions --pg-user … --no-verify`
  boots and `init_schema` creates `option_snapshot`.
- Browser → **standby/empty** state. Select NIFTY + BANKNIFTY → **Fetch Data** → workers start,
  rows land in `option_snapshot`, the table populates **from the DB**, WS pushes each new
  `nse_timestamp` (timestamp-dedup honoured). `GET /api/fetch/status` shows running + last writes;
  **Stop** cancels cleanly.
- **Backend offline tests** monkeypatch the worker's `api.response` with committed fixtures
  (`tests/fixtures/nse_nifty_sample.json` + `nse_market_closed.json`); assert `write_snapshot`
  dedups via `ON CONFLICT`, `reader` rebuilds `ChainOut`, and `series` yields the multi-snapshot
  time series. Greeks checked via put-call parity `C−P = S−K·e^(−rt)`; max-pain/payoff known-answer.
  Use a transactional/throwaway test DB (or a thin fake pool for units + one DB-gated integration test).
- **Frontend**: vitest/RTL renders mirrored CALL|STRIKE|PUT + ATM and the `SymbolSelector`/
  `FetchDataButton` states (idle/running/error); `HeatCell` snapshot asserts min→`#F8696B`,
  mid→`#FFEB84`, max→`#63BE7B`; MSW stubs `/api/*` (incl. fetch endpoints) + WS.

## Risks & mitigations
NSE anti-bot cookies now handled by v3 `core` warm-up — drop the bespoke prime. · One shared
`asyncio.Semaphore(max_concurrent)` caps concurrent NSE fetches across all worker tasks. ·
Timestamp dedup in the worker + `UNIQUE(symbol,expiry,nse_timestamp)` as the correctness safety net
(`ON CONFLICT DO NOTHING`). · DB unreachable at boot → `health` surfaces it; data routes 503 until
snapshots exist; UI shows the standby state. · Long-running worker tasks cancelled cleanly on Stop
and on shutdown. · `verify=False` default matches the repo. · all `requests`/`pandas` via
`asyncio.to_thread`, all DB via asyncpg. · market-closed/empty → `no_data` flags + last-good
snapshot + UI banner. · PCR div-by-zero guarded. · CORS only under `--dev`. · MVP scope is **indices
only** (NIFTY, BANKNIFTY, MIDCPNIFTY, NIFTYNXT50, FINNIFTY); equities deferred (matches async MVP).
