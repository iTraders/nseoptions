<div align = "center">

# API Correction - Migrate nseoptions to the NSE Option Chain v3 API

</div>

<div align = "justify">

## Context

The *nseoptions* package fetches option-chain data from NSE India and feeds `main.py`, which polls the API all day and
writes a live Excel view (xlwings) plus raw JSON dumps. The package was built against the legacy REST endpoints
(`/api/option-chain-indices?symbol=X`, `/api/option-chain-equities?symbol=X`). A live probe today (2026-06-12) confirms
the legacy endpoint is **decommissioned - HTTP 404 with or without cookies**. The site now uses a new API pair, verified
both live from this machine and in four maintained OSS libraries (jugaad-data, stock-nse-india, NseIndiaApi, VarunS2002):

  1. `GET https://www.nseindia.com/api/option-chain-contract-info?symbol=NIFTY` - returns `{expiryDates: [...], strikePrice: [...]}` (expiry format `DD-Mon-YYYY`, e.g. `16-Jun-2026`).
  1. `GET https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol=NIFTY&expiry=16-Jun-2026` - returns the chain for **one expiry only**; `type=Indices` for indices, `type=Equity` (singular) for stocks.

Live-probed facts that drive the design:

  * A real browser `user-agent` is **mandatory** - the default python-requests UA makes NSE hang until ReadTimeout (no HTTP error). Cookie warm-up (`GET https://www.nseindia.com/option-chain`, sets `_abck`/`bm_sz`/`nsit`) was optional today but all maintained clients do it; keep it as belt-and-braces and re-warm on `401/403/JSONDecodeError`.
  * v3 response envelope matches legacy (`records` + `filtered`, same `timestamp` format `12-Jun-2026 12:33:49`, same `filtered.CE/PE.totOI/totVol`), **except** the per-leg fields `bidQty/bidprice/askQty/askPrice` are gone, replaced by `buyQuantity1/buyPrice1/sellQuantity1/sellPrice1`. CE/PE legs also gained `optionType` and a duplicate `PChange` (keep `pChange`).
  * Machine gotcha: env var `CURL_CA_BUNDLE='""'` (broken) makes requests crash with OSError unless `verify=` is passed **per-request** (the current per-request pattern must be preserved; session-level `verify` is defeated).
  * `modules/prettify` is an uninitialized gist submodule in this checkout - `main.py` crashes at `import prettify` before any API call.

Scope per user decision: **core fix + code hygiene inside existing files, no new project files**. Expiry UX: validate
against contract-info, show the list, blank input defaults to nearest expiry. All Python edits follow the
`/python-code-format` skill (4-space indent, `arg : type = default` spacing, reST docstrings, `# !`/`# ?` tags,
`# ..versionchanged:: 2026-06-12` annotations, preserve existing lowercase public names like `setconfig`/`makeclean`).

## File Changes

### 1. nseoptions/config/default.yaml (Full Replacement)

```yaml
about:
  name: NSE Options Configuration File
  description: |
    NSE Options is a web application that provides a simple interface to view and analyze NSE options data. The
    configuration file is used to set the application settings - like the header contents, default URL settings and
    other relevant informations.
  version: 2.0.0

config:
  # default settings, can be overridden by the user by providing the same structure
  # else, the application will use these settings as default for the application
  header:
    accept: "*/*"
    accept-language: en-US,en;q=0.9,en-IN;q=0.8

    # ? only advertise encodings `requests` can decode natively (no br/zstd)
    accept-encoding: gzip, deflate

    # ! a real browser user-agent is mandatory - the default python-requests UA
    # makes NSE hang until ReadTimeout; periodically update as per the website::
    # open browser > inspect element > network tab > refresh page > request headers
    user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36
    referer: https://www.nseindia.com/option-chain

  # option chain url for data scrapping/api usage
  # ..versionchanged:: 2026-06-12 Migrate to NSE v3 Option Chain API
  # ! legacy `option-chain-indices`/`option-chain-equities` are decommissioned (404)
  uri:
    base: https://www.nseindia.com/api/

    # ? cookie warm-up page, hit once per session to collect akamai cookies
    warmup: https://www.nseindia.com/option-chain

    # ? expiry discovery endpoint, returns `expiryDates` and `strikePrice`
    contract: "option-chain-contract-info?symbol={symbol}"

    type:
      index: "option-chain-v3?type=Indices&symbol={symbol}&expiry={expiry}"
      stock: "option-chain-v3?type=Equity&symbol={symbol}&expiry={expiry}"
```

### 2. nseoptions/core.py (NSEOptionChain)

Add `import datetime as dt` (stdlib group) and `from nseoptions.processing import normalizeexpiry` (local group; no
cycle - `__init__.py` loads *processing* before *core*, and *processing* never imports *core*).

  * `__init__(self, symbol : str, expiry : str | dt.date | None = None, **kwargs) -> None` - keep `verify` kwarg; add `timeout` kwarg (default 15), `self.session = None`, and `self.expiry = normalizeexpiry(expiry) if expiry else None` (the docstring already promises `expiry`; now implement it). No network in `__init__`.
  * `setconfig(self, file : str = CONFIG, type : str = "index", **kwargs) -> dict` - keep the signature (public API; `# ?` note the builtin shadowing, do not rename). Load YAML via `with open(...)` + `yaml.safe_load` (fixes handle leak). Keep header override and `self.URI_HEADER`. Set `self.NSE_WARMUP_URI`, `self.NSE_CONTRACT_URI` (formatted with symbol), store the chain template unformatted as `self._apiuri`, and build `self.NSE_API_URI` immediately only when `self.expiry` is already set. Return config.
  * New `setexpiry(self, expiry : str | dt.date) -> str` - normalize, lazily call `setconfig()` if `_apiuri` missing, rebuild `NSE_API_URI`, return the canonical string.
  * New `expiries(self) -> list[str]` - lazy `setconfig()` guard; ensure session; `GET NSE_CONTRACT_URI` with `timeout`/`verify` per-request + `raise_for_status()`; return `json()["expiryDates"]`; on first failure discard the session, re-warm, retry once.
  * New private `__newsession__(self) -> None` - `requests.Session()`, `session.headers.update(self.URI_HEADER)`, warm-up `GET NSE_WARMUP_URI` (`# !` comment: `verify=`/`timeout=` must stay per-request because of the broken `CURL_CA_BUNDLE` env var).
  * `response(self, waittime : int = 10, maxretries : int = 30) -> dict` - guard: raise `ValueError("expiry not set - call setexpiry() before response()")` when `NSE_API_URI` is unbuilt. Replace the infinite loop with `for count in range(1, maxretries + 1)`: ensure session; `GET` with `timeout`/`verify`; `raise_for_status()`; `r.json()`; sanity check `"records"` and `"filtered"` keys present else raise `ValueError`. On success return. Catch `KeyboardInterrupt` first and re-raise (clean Ctrl+C); on any other exception set `self.session = None` (forces cookie re-warm), print the existing failure line, keep the tqdm countdown of `waittime` seconds. After the loop raise `ConnectionError(f"NSE v3 fetch failed after {maxretries} attempts")` (with `waittime=20` from `main.py` that is ~10 min of outage tolerance).

### 3. nseoptions/processing.py (OptionChainProcessing)

  * New module-level `normalizeexpiry(expiry : str | dt.date) -> str` - `dt.date` -> `strftime("%d-%b-%Y")`; `str` -> `strptime(expiry.strip().title(), "%d-%b-%Y")` round-trip back to `strftime("%d-%b-%Y")` (fixes case and zero-padding so string comparison with API rows is exact); raise `ValueError` with a clear format message. Shared by `core.setexpiry`.
  * `__init__` - `self.expiry = normalizeexpiry(expiry)` replaces the raw passthrough. Everything else unchanged (v3 keeps `records.timestamp` format and `records.underlyingValue` - verified live).
  * `makeclean()` -
      * PCR zero guard: `self.put_call_ratio = self.tot_oi_pe / self.tot_oi_ce if self.tot_oi_ce else float("nan")` (CE totOI is 0 pre-open; xlwings writes NaN as a blank cell).
      * **The column fix**: in the 14-name `columns` list replace the last four entries `bidQty, bidprice, askQty, askPrice` with `buyQuantity1, buyPrice1, sellQuantity1, sellPrice1` - same positions, so the Excel template needs zero edits (`# !` comment: order is load-bearing for the template).
      * `frame.drop(columns = dropcols, inplace = True, errors = "ignore")` on both drop calls (hardening; all four dropcols still exist in v3 legs).
      * Empty-frame guard after the expiry/strike filter: raise `ValueError` naming `self.expiry` and `response["records"]["expiryDates"]` so a wrong expiry can never again produce a silently empty Excel.
      * Keep the **inner** merge (current behavior); add a `# ?` comment documenting the `how = "outer"` + sort alternative for one-sided strikes.
      * `# ?` comment on the flatten loop: v3 item-level key is `expiryDates` (plural) but the loop only consumes CE/PE legs which still carry `expiryDate` - do not "fix". The duplicate `PChange`/`optionType` v3 keys are dropped automatically by the final 29-column selection.
  * `imultiple` becomes `@staticmethod` (drops unused `self`; existing `self.imultiple(symbol)` call still works).

### 4. main.py

  * Build the parser and call `args = parser.parse_args()` **before** any `input()` (fixes `python main.py --help` hanging on the symbol prompt). Keep `--no-verify` as-is.
  * Wrap the prettify import in `try/except ImportError` with a tiny `textAlign` print-fallback shim (this checkout has an uninitialized submodule); also run `git submodule update --init` during implementation to restore the real one.
  * Remove `import numpy as np` and `np.set_printoptions(...)` (dead).
  * New expiry resolution replacing the blind input: `validexpiry = API.expiries()`; print the first ~8 dates; loop: `input(f"Enter the Expiry (DD-MMM-YYYY) [{validexpiry[0]}]: ") or validexpiry[0]` -> `API.setexpiry(...)` (catch `ValueError` -> re-prompt on bad format) -> membership check against `validexpiry` (re-prompt if unlisted). The canonical string feeds the output filename and `OptionChainProcessing` unchanged.
  * Wrap the polling loop: `except KeyboardInterrupt` -> print stop message, exit 0 (covers Ctrl+C in countdowns and in-flight fetches); `except ConnectionError` -> print and `sys.exit(1)` (the new retry cap surfaces here instead of looping forever).
  * Template copy, xlwings `writefile` (intentionally never saved - live view), `writejson`, and the 30 s refresh countdown stay byte-identical.

### 5. nseoptions/__init__.py and requirements.txt

  * `__version__` bump to `v0.1.0.dev0` with a `# ..versionchanged:: 2026-06-12` annotation.
  * `requirements.txt`: remove `swifter==1.4.0` (unused); add `PyYAML==6.0.2` (imported by core but never declared); keep the other five pins.

## Column Mapping (Excel Template Unchanged, A..AC = 29 Columns at A12)

| Position | Legacy Field | v3 Field |
| :---: | :---: | :---: |
| 1-10 per side | openInterest ... totalSellQuantity | unchanged |
| 11 | `bidQty` | `buyQuantity1` |
| 12 | `bidprice` | `buyPrice1` |
| 13 | `askQty` | `sellQuantity1` |
| 14 | `askPrice` | `sellPrice1` |

Metric cells stay valid: `A1`/`AC1` (tot OI) over `openInterest_ce/_pe`, `D1`/`Z1` (tot vol) over
`totalTradedVolume_ce/_pe`, `O1` underlying + timestamp, `O3` PCR.

## Bugs Fixed (From the Audit)

  * Dead endpoint migration (critical) - core.py:85, default.yaml.
  * Infinite retry loop, no timeout, fresh Session per attempt losing cookies (critical) - `core.response()`.
  * `setconfig()` footgun: lazy guards in `setexpiry()`/`expiries()`; `response()` raises a clear `ValueError` instead of `AttributeError`.
  * YAML handle leak + unsafe loader - `core.setconfig()`.
  * `--help` blocked by `input()` - main.py:82-95.
  * Unvalidated expiry producing silently empty output - main.py + empty-frame guard in `makeclean()`.
  * `ZeroDivisionError` on pre-open PCR - processing.py:158.
  * Stale v3 column names crashing the final selection - processing.py:210-230.
  * No graceful Ctrl+C - main.py loop.
  * Missing PyYAML pin, stale swifter pin - requirements.txt.

Deferred as optional extras (explicitly out of scope, no new project files): outer merge toggle, tests/, pyproject.toml,
.flake8, URL-quoting equity symbols containing `&` (e.g. `M&M`), logging framework, market-hours awareness.

## Implementation Order (Python Coding Agents, Per User Confirmation)

Each step ends with a git commit (see Commit Strategy) so the implementation is tracked step-by-step.

  1. **Step 0** - copy this plan into `.claude/plans/API Correction.md` (markdown-format skill) and `git submodule update --init`; commit the plan.
  1. **Code agent A** - `nseoptions/config/default.yaml` + `nseoptions/core.py` (fetch layer), applying `/python-code-format`; commit.
  1. **Code agent B** - `nseoptions/processing.py` (after A, imports `normalizeexpiry` contract), applying `/python-code-format`; commit.
  1. **Code agent C** - `main.py` + `nseoptions/__init__.py` (version bump), applying `/python-code-format`; commit. Then `requirements.txt`; separate commit.
  1. **Review agent** - adversarial review of the full diff: skill compliance (spacing, docstrings, tags), the column-order invariant, per-request `verify`/`timeout` preservation, import-cycle check. Fixes (if any) get their own commit.
  1. **Verify** - run the verification steps below; any resulting fix is committed individually.

## Commit Strategy (/git-commiter Skill, Per User Instruction)

A detailed commit after every important step, following the *git-commiter* skill exactly: emoji-prefixed subject
(vocabulary glyphs only, lowercase imperative, <= 72 chars), structured `Why / What / Style / Verification` body,
written to `.git/COMMIT_MSG.txt` and committed via `git commit -F` (never `-m` on Windows), explicit `git add <file>`
per the per-file policy, `git log --oneline -1` inspection after each commit. Trailers: `Co-authored-by: Copilot`
(skill-mandated) plus `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. Planned commit sequence:

  1. `📜 docs(plans): add nse v3 api correction plan` - the plan copy in `.claude/plans/API Correction.md`.
  1. `🐛🛠️ fix(core): migrate fetch layer to nse option-chain-v3 api` - `default.yaml` + `core.py` (warmed session, capped retries, expiry discovery).
  1. `🐛 fix(processing): remap v3 fields and guard pcr and empty frames` - `processing.py`.
  1. `🐛🛠️ fix(cli): argparse ordering, expiry validation and graceful exit` - `main.py` + `__init__.py` version bump.
  1. `🤖 build(deps): drop unused swifter and declare pyyaml` - `requirements.txt`.

## Verification

  1. `python -m compileall nseoptions main.py` and `python -c "import nseoptions; print(nseoptions.__version__)"` - clean imports, no cycle.
  1. `python main.py --help` - prints usage and exits without prompting (regression for the argparse fix).
  1. Discovery smoke: `python -c "from nseoptions import NSEOptionChain; api = NSEOptionChain('NIFTY'); api.setconfig(); print(api.expiries()[:5])"` - expect `['16-Jun-2026', ...]`; exercises warm-up, headers, and the per-request `verify` path on this `CURL_CA_BUNDLE`-broken machine.
  1. Chain smoke: `api.setexpiry(api.expiries()[0]); r = api.response(waittime = 5)` - expect keys `records`/`filtered`, fresh timestamp, >0 rows; feed into `OptionChainProcessing('NIFTY', '', r, api.expiry)` and assert `makeclean()` returns exactly 29 columns with `buyQuantity1_ce` at index 10 and no `bidQty`/`askPrice` names anywhere.
  1. Negative paths: bad-format expiry (`99-Foo-2026`) raises `ValueError`; valid-format-but-unlisted expiry re-prompts in `main.py`; `OptionChainProcessing` with a wrong expiry raises the available-expiries `ValueError`; `normalizeexpiry('16-jun-2026') == '16-Jun-2026'`.
  1. End-to-end (market hours, today until 15:30 IST): `python main.py --no-verify`, default NIFTY, accept nearest expiry; confirm the verbose block, a JSON file per cycle in `output/<today>/`, and the live xlsx filling A12:AC52 with metrics at `O1/O3/A1/AC1/D1/Z1`, refreshing each cycle, workbook never saved.
  1. Resilience: let it poll past the ~60 s cookie window (>= 5 cycles) - any failure must surface as a single retry line then recover via session re-warm; Ctrl+C during the countdown and during a fetch must exit cleanly with no traceback.
  1. Fresh venv: `pip install -r requirements.txt` then repeat step 1 (validates the PyYAML addition and swifter removal).

## Key Risks

  * NSE/Akamai behavior is volatile - warm-up may become mandatory or stricter; mitigated by always warming and re-warming on failure, all endpoints config-overridable in YAML.
  * `response()` now fails after ~10 minutes of continuous outage instead of retrying forever - intentional behavior change, surfaced cleanly in `main.py`.
  * PCR writes a blank cell (NaN) at `O3` pre-open - confirm no template formula chokes on a blank (fallback: `0.0`).
  * Inner merge still drops one-sided strikes (rare near ATM with `nstrikes = 20`) - preserved deliberately, outer-merge documented as the follow-up.

</div>
