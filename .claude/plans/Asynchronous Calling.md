# Asynchronous NSE Options Data Service — v1 MVP Plan

## Context

The current `main.py` runs as a single-symbol, interactive, synchronous CLI. The v1 MVP
evolves this into a long-running async service that:

- Fetches option chain data for all major NSE index derivatives **and all their live expiries**
  concurrently from a single `nseoptions` CLI invocation
- Writes new snapshots to **PostgreSQL** only when NSE data has actually changed
  (timestamp-based deduplication to avoid redundant writes across NSE's ~3-minute refresh cadence)
- Is **pip-installable** (`pip install nseoptions`) exposing the `nseoptions` console command
- Preserves the `--no-verify` flag for SSL-bypass environments
- Remains fully decoupled from the DB schema (writer is a stub until the DB project delivers
  the schema); the ReactJS dashboard on `feature/dashboard` reads from that same DB

This plan covers architecture and file structure only. No code is written yet. DB schema
definition is owned by a separate project — this plan specifies only the writer contract
(inputs/outputs) so both projects can align independently.

---

## Development Guidelines

### Code Format & Skill Requirement

**All Python code must follow the `/python-code-format` skill.** This ensures consistency
across all new files (`cli.py`, `worker.py`, `db.py`) and any modifications to existing
modules. Always read the full file before writing or modifying any Python code.

### Agent Deployment

**Deploy all Python coding agents from the global directory** for this project. Use the
`python-code-format` skill when creating or editing Python files to ensure adherence to
the project's formatting standards.

### Git Commit Strategy

Create **detailed, atomic git commits at each important interval/step**:
- One commit per file creation (with meaningful `feat:` or `chore:` prefix)
- One commit after completing a logical feature block (e.g., "all CLI args parsed and validated")
- One commit after each smoke-test cycle
- Commit messages should reference the task/issue being addressed and summarize what changed
- Include `Co-Authored-By` footer for transparency

This allows graceful tracking and cherry-picking of changes if needed.

---

## Architecture Overview

```
pip install nseoptions
  └── registers CLI entrypoint: nseoptions = "nseoptions.cli:main"

nseoptions --hostname <host> --database <db> --username <user> --password <pw> [--no-verify]
  │
  ├── cli.py :: main()
  │     parse args → warn if --no-verify → asyncio.run(run_service(args))
  │
  └── cli.py :: run_service(args)         [async, runs forever until CTRL+C]
        │
        ├── db.py :: create_pool(...)      create asyncpg connection pool
        │
        ├── for each symbol in DEFAULT_SYMBOLS (or --symbols override):
        │     NSEOptionChain.expiries()    one-time at startup, sync → to_thread
        │
        ├── asyncio.Semaphore(max_concurrent=3)   IP-level rate-limit guard
        │
        └── asyncio.gather(*tasks)
              │
              └── worker.py :: symbol_worker(symbol, expiry, semaphore, db_pool, …)
                    loop forever:
                      async with semaphore:
                        response = await to_thread(api.response, waittime=20)
                      if response["records"]["timestamp"] == last_seen → sleep, continue
                      model = OptionChainProcessing(…); opchain = model.makeclean()
                      await db.write_snapshot(pool, symbol, expiry, response, model, opchain)
                      last_seen = nse_timestamp
                      await asyncio.sleep(interval)   # default 30 s (matches main.py)
```

**Key design decision — `asyncio.to_thread()` over `aiohttp`**: The existing
`NSEOptionChain` uses `requests.Session` with Akamai cookie warm-up. Rewriting to
`aiohttp` would require duplicating that session-warm logic. Wrapping with
`asyncio.to_thread()` keeps all existing retry/re-warm logic intact with zero changes
to `core.py`.

---

## Default Symbols (Indices Only for MVP)

```python
DEFAULT_SYMBOLS = ["NIFTY", "BANKNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "FINNIFTY"]
```

Override at runtime with `--symbols NIFTY BANKNIFTY`. Each symbol's `setconfig(type=…)`
defaults to `"index"`; equity support is deferred to v2.

---

## Files to Create

### 1. `pyproject.toml` (new — root of repo)

No `setup.py` or `pyproject.toml` exists. This is required for `pip install nseoptions`
to register the `nseoptions` CLI command.

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "nseoptions"
version = "0.1.0.dev0"
description = "Asynchronous NSE F&O Option Chain Data Service"
requires-python = ">=3.11"
dependencies = [
    "pandas>=2.2",
    "PyYAML>=6.0",
    "requests>=2.32",
    "tqdm>=4.67",
    "urllib3>=2.2",
    "asyncpg>=0.29",
]

[project.optional-dependencies]
excel = ["xlwings>=0.33"]     # legacy main.py only

[project.scripts]
nseoptions = "nseoptions.cli:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["nseoptions*"]

[tool.setuptools.package-data]
nseoptions = ["config/*.yaml"]
```

`asyncpg` is the async PostgreSQL driver (faster than psycopg2 for pure-async workloads,
avoids GIL contention). `xlwings` is demoted to an optional extra so the server-side
service has no Excel dependency.

### 2. `nseoptions/cli.py` (new)

Argparse entrypoint + top-level async runner.

**Signature:** `main() -> None`  (registered as console_scripts entry point)

**Arguments:**

| Flag | Type | Default | Notes |
|------|------|---------|-------|
| `--hostname` | str | required | PostgreSQL host |
| `--database` | str | required | DB name |
| `--username` | str | required | DB user |
| `--password` | str | required | DB password |
| `--port` | int | 5432 | PostgreSQL port |
| `--symbols` | str… | DEFAULT_SYMBOLS | Override the index list |
| `--interval` | int | 30 | Poll interval in seconds |
| `--max-concurrent` | int | 3 | Semaphore cap — concurrent NSE fetches |
| `--no-verify` | flag | verify=True | Bypass SSL; warns once + disables urllib3 spam |

**`run_service(args)` responsibilities:**

1. Create `asyncpg` connection pool via `db.create_pool()`
2. For each symbol: call `NSEOptionChain(symbol, verify=args.verify).expiries()` (wrapped in
   `asyncio.to_thread`) to get the live expiry list at startup
3. Build one `asyncio.Task` per `(symbol, expiry)` pair via `worker.symbol_worker(…)`
4. `await asyncio.gather(*tasks)` — runs until `KeyboardInterrupt`, then cancels all tasks
5. Print startup summary: `"Started N workers across M symbols (X expiries each)"`

**Graceful shutdown:** wrap gather in `try/except KeyboardInterrupt` → cancel tasks →
`await pool.close()` → `sys.exit(0)`.

### 3. `nseoptions/worker.py` (new)

Per-`(symbol, expiry)` async infinite-loop worker.

**Signature:** `async def symbol_worker(symbol, expiry, semaphore, db_pool, verify, interval) -> None`

**Loop body:**

1. Instantiate `NSEOptionChain(symbol, verify=verify)` once before the loop; call
   `setconfig()` and `setexpiry(expiry)`.
2. `async with semaphore:` → `response = await asyncio.to_thread(api.response, waittime=20)`
   - On `ValueError` or `ConnectionError`: log `[symbol/expiry] error`, `await sleep(interval)`, `continue`
   - Re-raise `KeyboardInterrupt` (do not swallow it)
3. Dedup check: compare `response["records"]["timestamp"]` against `last_nse_timestamp`
   (local variable per coroutine, initialised to `None`).
   If equal → `await sleep(interval)`, `continue`.
4. Update `last_nse_timestamp`.
5. `model = OptionChainProcessing(symbol, apikey="", response=response, expiry=expiry)`
6. `opchain = model.makeclean(verbose=False)`
   - On `ValueError` (expiry not in data): log, `await sleep(interval)`, `continue`.
7. `await db.write_snapshot(db_pool, symbol, expiry, response, model, opchain)`
8. `await asyncio.sleep(interval)`

**Isolation:** Each `NSEOptionChain` instance has its own `requests.Session`. The existing
`core.py` session re-warm logic (`self.session = None` on failure, re-`__newsession__`) is
preserved unchanged because the whole `api.response()` call runs in a thread.

### 4. `nseoptions/db.py` (new — stub)

Database writer interface. The body of `write_snapshot` is `raise NotImplementedError` until
the DB schema is delivered by the DB team. The function signature defines the contract.

```python
async def create_pool(hostname, port, database, username, password):
    """Return an asyncpg.Pool. Raises if PostgreSQL is unreachable."""
    import asyncpg
    return await asyncpg.create_pool(
        host=hostname, port=port, database=database,
        user=username, password=password,
        min_size=2, max_size=10
    )


async def write_snapshot(pool, symbol: str, expiry: str, response: dict, model, opchain) -> None:
    """
    Write one option chain snapshot to the database.

    DB contract (schema to be defined by DB project):
      symbol           VARCHAR(50)     e.g. "NIFTY"
      expiry           DATE            e.g. 2026-06-19
      nse_timestamp    TIMESTAMP       from response["records"]["timestamp"]
      fetched_at       TIMESTAMP       UTC wall-clock at write time
      underlying       NUMERIC(12,4)   model.underlying (spot price)
      tot_oi_ce        BIGINT          model.tot_oi_ce
      tot_oi_pe        BIGINT          model.tot_oi_pe
      tot_vol_ce       BIGINT          model.tot_vol_ce
      tot_vol_pe       BIGINT          model.tot_vol_pe
      put_call_ratio   NUMERIC(8,4)    model.put_call_ratio
      raw_response     JSONB           full API payload (audit / dashboard use)
      opchain_rows     JSONB           opchain.to_dict("records") — cleaned strikes

    Dedup constraint (suggested): UNIQUE(symbol, expiry, nse_timestamp)
    Application-level dedup in worker.py guards against most redundant calls;
    this DB constraint is the safety net.
    """
    raise NotImplementedError("DB writer not yet implemented — schema pending")
```

---

## Files to Modify

### `nseoptions/__init__.py`
No changes required. `NSEOptionChain` and `processing` are already exported.

### `nseoptions/core.py`
No changes. `asyncio.to_thread()` wraps the synchronous API; `core.py` is untouched.

### `nseoptions/processing.py`
No changes.

### `main.py`
No changes. Legacy single-symbol CLI stays intact as a standalone script.

### `requirements.txt`
Keep as-is for `main.py` users who install manually. `pyproject.toml` is the authoritative
dependency source for `pip install nseoptions`.

---

## Deduplication Strategy

NSE refreshes option chain data approximately every 3 minutes. The service polls every 30 s
to catch updates promptly. The dedup check prevents redundant DB writes:

1. **Application layer (worker.py)**: `response["records"]["timestamp"]` is a string in
   `"%d-%b-%Y %H:%M:%S"` format e.g. `"13-Jun-2026 12:33:49"`. If equal to the last seen
   value for this `(symbol, expiry)` coroutine, skip processing entirely (no DB round-trip).
2. **DB layer (db.py)**: `UNIQUE(symbol, expiry, nse_timestamp)` catches any race condition
   (e.g. service restart with in-flight state, or duplicate task spawning).

The application-layer check is the performance guard; the DB constraint is the correctness guard.

---

## Concurrency and Rate-Limit Safety

- `asyncio.Semaphore(max_concurrent=3)` is shared across all workers; only 3 NSE HTTP
  fetches run at any moment regardless of how many `(symbol, expiry)` tasks exist.
- 5 default symbols × ~10 expiries each = ~50 tasks, but only 3 hit NSE at once per poll cycle.
- Each `NSEOptionChain` instance has its own session (independent Akamai cookies). No
  session sharing across workers.
- `--max-concurrent` is user-tunable if NSE tightens rate limits.

---

## Known Deferred Items (out of v1 scope)

| Item | Reason |
|------|--------|
| Equity F&O symbols (`type="stock"`) | Scale/Akamai risk; indices cover primary use case |
| Expiry refresh after startup | Expiries are stable within a session; weekly restart acceptable |
| DB schema implementation | Owned by separate DB project |
| Market-hours awareness | Service can run 24/7; NSE returns stale data outside hours |
| `tests/` test suite | Explicitly deferred per `MIGRATION_COMPLETE.md` |
| `--discover` flag for full F&O universe | Post-v1; needs NSE symbol-list endpoint research |

---

## Implementation Checklist

Progress tracking for v1 MVP development. Check off items as they are completed.

### Phase 1: Project Setup
- [ ] Create `pyproject.toml` at repo root with all build config and dependencies (commit: `feat(build): add pyproject.toml`)
- [ ] Verify `pip install -e .` works and `nseoptions --help` is accessible

### Phase 2: CLI Module (`nseoptions/cli.py`)
- [ ] Write `cli.py` with argparse setup for all required flags (hostname, database, username, password, etc.)
- [ ] Implement `main()` entrypoint function
- [ ] Implement `run_service(args)` async coroutine with startup/shutdown logic
- [ ] Add SSL warning logic (wrap existing code from `main.py`)
- [ ] Add startup summary logging: `"Started N workers across M symbols"`
- [ ] Test graceful KeyboardInterrupt handling and pool cleanup (commit: `feat(cli): implement argparse and async runner`)

### Phase 3: Database Module (`nseoptions/db.py`)
- [ ] Write `db.py` with `create_pool()` and `write_snapshot()` stub functions
- [ ] Document DB contract in `write_snapshot()` docstring (field names, types, constraints)
- [ ] Ensure `write_snapshot()` raises `NotImplementedError` with clear message (commit: `feat(db): add writer stub with contract definition`)

### Phase 4: Worker Module (`nseoptions/worker.py`)
- [ ] Write `worker.py` with `async def symbol_worker(...)` coroutine
- [ ] Implement NSEOptionChain initialization and setconfig/setexpiry calls
- [ ] Implement dedup check logic (compare `response["records"]["timestamp"]`)
- [ ] Add error handling: `ValueError`, `ConnectionError` → log and retry
- [ ] Integrate `OptionChainProcessing.makeclean()` call
- [ ] Integrate `db.write_snapshot()` call
- [ ] Implement graceful loop with `asyncio.sleep(interval)` (commit: `feat(worker): implement per-expiry async loop with dedup`)

### Phase 5: Integration & Testing
- [ ] Update imports in `nseoptions/__init__.py` if needed (likely no changes)
- [ ] Install package in editable mode: `pip install -e .`
- [ ] Run smoke test with `--symbols NIFTY --interval 10 --max-concurrent 1 --no-verify`
- [ ] Verify startup output: SSL warning, expiry fetch, worker count summary
- [ ] Verify graceful shutdown on CTRL+C (no hanging tasks)
- [ ] Verify dedup logic: same timestamp → skip DB write (monitor logs)
- [ ] Create integration test commit: `test(smoke): verify startup, expiry fetch, dedup, graceful shutdown`

### Phase 6: Documentation & Polish
- [ ] Verify all docstrings match code behavior
- [ ] Add inline comments only where WHY is non-obvious (per project guidelines)
- [ ] Verify error log messages are actionable (e.g., `[NIFTY/16-Jun-2026] Connection error: ...`)
- [ ] Final polish commit: `docs: finalize docstrings and inline comments`

---

## Verification (after implementation)

```shell
# Install in editable mode
pip install -e .

# Smoke test — DB stub will raise NotImplementedError per snapshot, but
# startup, symbol discovery, expiry fetch, and dedup logic should all work
nseoptions \
  --hostname localhost --database nseoptions \
  --username postgres --password postgres \
  --symbols NIFTY --interval 10 --max-concurrent 1 --no-verify
```

Expected output:
```
UserWarning: SSL certificate verification is DISABLED via `--no-verify`.
  >> NIFTY: fetched 10 expiries
Started 10 workers across 1 symbols.
[NIFTY/16-Jun-2026] NotImplementedError: DB writer not yet implemented — schema pending
...
```

Once `db.py::write_snapshot()` is implemented, replace `localhost` with the real PostgreSQL
coordinates and verify rows appear in the target table with a `UNIQUE(symbol, expiry, nse_timestamp)`
constraint enforced.
