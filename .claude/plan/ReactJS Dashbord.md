# NSE Options — Production ReactJS Dashboard

> Approved implementation plan. Tracks the architecture, decisions, and phased build of a
> production-grade ReactJS dashboard served by a FastAPI backend, launched via `python dashboard.py`.

## Context
`nseoptions` fetches & cleans NSE India option-chain data, today rendered only into an Excel
template (`main.py` → `writefile`). This project adds a modern, **production-grade ReactJS dashboard**
(served by a Python backend) delivering four capabilities:

1. **Live option chain** — Sensibull-style heatmap table mirroring the Excel layout.
2. **Historic price tracking** — per-strike time series of LTP / OI / IV across a session.
3. **Strategy builder** — multi-leg payoff / greeks / breakeven analyzer.
4. **Auto-suggest** — analyze the current scenario (PCR, max-pain, OI buildup, IV) and recommend strategies.

**Hard constraint:** `nseoptions/core.py` and `nseoptions/processing.py` are being refactored on
another branch — **do not modify them**. We only consume their public API and add NEW files.

## Locked decisions
- **Interpreter:** project runs on Python **3.13** (Anaconda); the module already uses `X | Y` union syntax (needs ≥3.10).
- **Frontend:** Vite + React + TypeScript + TailwindCSS + shadcn/ui. Industry-grade, reusable components.
- **Backend:** FastAPI + Uvicorn (native async WebSocket fan-out, pydantic = typed contract, `StaticFiles` SPA mount, threadpool offload for the blocking sync API). Greeks via `math.erf` — **no scipy**.
- **Auto-suggest (IV):** deterministic **rules-based** engine behind a pluggable `SuggestionProvider` ABC so a `ClaudeSuggester` can slot in later with zero changes to `service.py`/`server.py`.
- **Live + history:** one backend NSE poller → in-memory cache → WebSocket fan-out to all clients; per-strike history persisted to **SQLite** (survives restarts).
- **Launch:** root-level `dashboard.py` run via `python dashboard.py` (argparse). **No pyproject/console-scripts now** (later).
- **Python style:** match the repo exactly (see below).

## Python style to match (studied in core.py / processing.py / main.py)
`# -*- encoding: utf-8 -*-` header · module docstring then `@author`/`@version`/`@copywright` ·
**spaces around `=` in kwargs** (`header = False`) · **spaces around `:` in annotations** (`response : dict`) ·
`# ?` and `# !` inline markers · grouped imports with trailing comments · full type hints ·
`dt` alias for datetime, `TQ` for tqdm · staticmethods where pure · gitmoji commit messages.

## Data contract (frozen — consume, never re-derive)
- `nseoptions.NSEOptionChain(symbol, verify=False)` → `.setconfig()` builds public `self.NSE_API_URI` + `self.URI_HEADER`; `.response(waittime)` → raw NSE JSON.
- Raw JSON: `records.{timestamp, underlyingValue, expiryDates[], data[].{strikePrice, expiryDate, CE{...}, PE{...}}}`, `filtered.{CE,PE}.{totOI,totVol}`.
- `nseoptions.processing.OptionChainProcessing(symbol, apikey, response, expiry, nstrikes=20)`:
  `.makeclean()` → 29-col DataFrame (14 CE | `strikePrice` | 14 PE **mirrored**) and sets attrs
  `underlying, timestamp, put_call_ratio, tot_oi_ce/pe, tot_vol_ce/pe, atm, lstrike, hstrike`.
- Per-leg fields: openInterest, changeinOpenInterest, pchangeinOpenInterest, totalTradedVolume,
  impliedVolatility, lastPrice, change, pChange, totalBuyQuantity, totalSellQuantity, bidQty, bidprice, askQty, askPrice.
- **No greeks exist** → compute via Black-Scholes from IV. Analytics use the **raw full `records.data[]`**
  (all strikes, both legs) while the table/PCR/totals reuse `makeclean()` + its attrs.
- `imultiple`: NIFTY 50, BANKNIFTY 100, MIDCPNIFTY 25, NIFTYNXT50 100, else 50.

## Design tokens (from `template/NSE Option Chain.xlsx`)
- Heatmap 3-stop (on %chng-in-OI / OI intensity): Red `#F8696B` → Yellow `#FFEB84` → Green `#63BE7B`.
- Layout: CALL block (OI/IV/LTP/VOLUME/CHNG/QTY/BID/ASK) left · STRIKE center · PUT block mirrored right; ATM row highlighted; sticky header + sticky strike column.
- Sensibull-style extras beyond Excel: Max-Pain bar, Support/Resistance OI walls, PCR gauge, IV smile.

## Architecture
```
nseoptions/dashboard/
  __init__.py     # package docstring + launch(symbol, expiry, host, port, verify, interval, nstrikes)
  settings.py     # frozen AppSettings dataclass (symbol, expiry, host, port, verify, interval, nstrikes, paths, dev)
  server.py       # create_app(settings): FastAPI, lifespan starts poller/SQLite, REST+WS routes, SPA static mount LAST
  service.py      # OptionChainService: single poller, in-memory snapshot cache, WS ConnectionManager, fan-out
  history.py      # HistoryStore: SQLite (WAL) per-strike LTP/OI/IV series, INSERT OR IGNORE idempotent
  analytics.py    # max_pain, oi_walls, black_scholes_greeks (math.erf), payoff_curve, iv_smile
  suggester.py    # SuggestionProvider ABC + RulesBasedSuggester (pluggable for ClaudeSuggester later)
  schemas.py      # pydantic v2 models = REST/WS contract
  frontend/       # Vite+React+TS+Tailwind+shadcn; build → frontend/dist served by server.py
dashboard.py      # root launcher, argparse, mirrors main.py idioms (--no-verify dest=verify)
requirements-dashboard.txt   # fastapi, uvicorn[standard], pydantic>=2  (requirements.txt untouched)
tests/            # offline fixtures + pytest; frontend vitest/RTL
```

### Backend service (the key piece)
- **Single poller**: one `NSEOptionChain` object; `poll_forever()` every `interval` (default 30s, jittered) does `fetch → makeclean → cache snapshot → history.write → broadcast`. New WS clients get the cached snapshot immediately — **never trigger a fetch**. Expiry/strike switches are pure cache reads.
- **Cookie-priming workaround (no core.py edit)**: service owns a persistent `requests.Session`, primes `https://www.nseindia.com/option-chain` to capture anti-bot cookies, then calls the public `self._api.NSE_API_URI` with `self._api.URI_HEADER`; falls back to `core.response()` on error.
- **Non-blocking**: all `requests`/`pandas`/`makeclean` via `asyncio.to_thread`; broadcast drops dead sockets.

### Endpoints
REST (`/api`): `health`, `meta` (symbol, expiryDates[], multiple, nstrikes, status), `chain?expiry=`,
`history?expiry=&strike=&leg=&field=`, `analytics?expiry=`, `POST strategy/payoff`, `suggestions?expiry=`.
WS `/ws?expiry=`: on connect `{type:snapshot,...}`; per tick `{type:tick,...}`; `{type:status,...}`; client `{type:subscribe,expiry}` (no NSE hit). 20s heartbeat + client backoff reconnect.
Pydantic: `LegQuote, StrikeRow, Greeks, ChainOut, AnalyticsOut, StrategyLeg, PayoffIn/Out, Suggestion, SuggestionsOut`.

### SQLite history schema
`option_history(symbol, expiry, strike, leg, ts, ltp, oi, chg_oi, iv, volume, underlying, UNIQUE(symbol,expiry,strike,leg,ts))`
+ index on lookup; `snapshot_meta(symbol,expiry,ts,pcr,max_pain,tot_oi_ce,tot_oi_pe,atm)`. WAL; DB at `output/history/<SYMBOL>.sqlite3` (reuses git-ignored `output/`).

### Algorithms (analytics.py)
- **Black-Scholes** (`σ=iv/100`, `r=0.065`, `t=max((expiry@15:30IST−now)/yr, 1e-6)`, `Φ` via `math.erf`): price/delta/gamma/theta(per-day)/vega(per-1%)/rho. Missing/zero IV → intrinsic-sign delta, others 0 + `iv_missing` flag; `t→0` → intrinsic, gamma/vega 0.
- **Payoff**: grid 0.9·minK→1.1·maxK (200 pts); per-leg intrinsic minus premium (posted `price` else LTP), signed by side × qty × lot; breakevens = sign-change interpolation; unbounded tails → `None`; net greeks summed at spot.
- **Max-pain** over all strikes: `argmin_E Σ CE_OI·max(E−K,0)+PE_OI·max(K−E,0)`; empty OI → `no_data`.
- **OI walls**: resistance = top CE-OI strikes ≥ ATM; support = top PE-OI strikes ≤ ATM (optionally weight by chng-OI).
- **Rules suggester**: `MarketContext{pcr, atm_iv, iv_regime, trend, dte, maxpain-gap}` → decision table (bull/bear call/put spreads, iron condor/short straddle, long straddle/strangle); each run through `payoff_curve` for P/L + breakevens; `rationale[]` lists firing conditions; sorted by `score`.

### Frontend (`frontend/src`)
- `lib/`: `api.ts` (typed fetch, zod-validated, base from `VITE_API_BASE`), `ws.ts` (reconnect/backoff), `heatmap.ts` (Red→Yellow→Green interpolation + luminance text color), `format.ts` (₹ lakh/crore), `greeks.ts`.
- `store/dashboard.ts` (**Zustand** UI-only: symbol, expiry, selectedStrike, builderLegs, heatmapMetric, theme). Server state in **TanStack Query**; `useChainSocket` writes WS ticks into the query cache.
- Reusable components: **OptionChainTable** (mirrored CALL|STRIKE|PUT, virtualized, sticky), **HeatCell** (the snapshot-tested heatmap unit), **PCRGauge, MaxPainChart, OIWallBar, IVSmileChart, KpiStat**, **StrikeHistoryChart**, **StrategyLegEditor/Row, PayoffChart, PayoffSummary, GreeksPanel**, **SuggestionCard/List, RationaleList**. shadcn/ui primitives under `components/ui`.
- Pages/tabs: Chain · History · Builder · Suggestions. Theme via Tailwind config + CSS vars (heatmap stops, atm highlight, profit/loss, dark-first).
- **Serving**: `vite build` → `frontend/dist`; `server.py` mounts it `html=True` after `/api`+`/ws`. Dev (`--dev`): Vite `:5173` + CORS to `:8000`; prod single-origin (no CORS). vite dev proxy forwards `/api`+`/ws` so paths are identical dev/prod.

### Root launcher `dashboard.py`
argparse `--symbol --expiry --host --port --interval --nstrikes --no-verify(dest=verify) --dev`; `sys.path.append` like main.py; calls `nseoptions.dashboard.launch(...)` which builds settings and `uvicorn.run`s.

## Phased plan (commit after each; gitmoji messages; deploy agents per phase)
0. `📝 add ReactJS dashboard plan` — write this file. ✅
1. **Backend skeleton & contract** — `settings.py`, `schemas.py`, `service.py` (poller+cache), cookie-priming, `__init__.launch`.
2. **History & analytics** — `history.py` (SQLite), `analytics.py` (BS via erf, max-pain, walls, payoff, iv-smile), `suggester.py`.
3. **Wire REST+WS + launcher** — `server.py` routes/lifespan/static, root `dashboard.py`, offline pytest fixtures.
4. **Frontend foundation** — Vite/TS/Tailwind/shadcn scaffold, design tokens, api client, ws hook, Zustand+Query, layout shell.
5. **Feature I — live heatmap** — OptionChainTable + HeatCell + ATM + sticky; PCRGauge/MaxPain/OIWall/IVSmile KPIs. Snapshot-verify hexes vs Excel.
6. **Features II/III/IV** — StrikeHistoryChart; StrategyBuilder + PayoffChart; SuggestionCards.
7. **Tests, build, docs, optimize** — vitest/RTL + HeatCell snapshot; serve built SPA; `requirements-dashboard.txt`; README dashboard section; review + optimization.

## Verification
- `python dashboard.py --symbol NIFTY` boots backend + serves SPA; open browser, confirm all 4 tabs.
- **Backend offline tests** with committed fixtures `tests/fixtures/nse_nifty_sample.json` (+ `nse_market_closed.json`); monkeypatch `_fetch_once`/`_prime_cookies` so no test hits the network. Greeks checked via put-call parity `C−P = S−K·e^(−rt)`; max-pain/payoff known-answer.
- **Frontend**: vitest/RTL renders mirrored CALL|STRIKE|PUT + ATM; `HeatCell` snapshot asserts min→`#F8696B`, mid→`#FFEB84`, max→`#63BE7B`; MSW stubs `/api/*`+WS. Periodic Playwright screenshot to compare color scale to the xlsx.

## Risks & mitigations
NSE anti-bot cookies → persistent primed session. · `verify=False` default matches repo. · single 30s jittered poller + backoff (no per-client fetch). · market-closed/empty → `no_data` flags, last-good snapshot, UI banner. · strike multiple per symbol reused from `imultiple`, exposed in `/api/meta`. · PCR div-by-zero guarded before `MarketContext`. · CORS only under `--dev`. · blocking calls via `asyncio.to_thread`. · SQLite WAL + single-writer + `INSERT OR IGNORE`.
