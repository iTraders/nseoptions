<h1 align = "center">NSE Option Chain</h1>

<div align = "center">

![GitHub Stars](https://img.shields.io/github/stars/iTraders/nseoptions?style=plastic)
![GitHub Forks](https://img.shields.io/github/forks/iTraders/nseoptions?style=plastic)
![GitHub Issues](https://img.shields.io/github/issues/iTraders/nseoptions?style=plastic)
![UNLICENSE File](https://img.shields.io/github/license/iTraders/nseoptions?style=plastic)

</div>

<div align = "justify">

The python library is designed to fetch the Option Chain data available in the [NSE India](https://www.nseindia.com/option-chain)
website. Please refer to the Terms and Conditions and Usages Policies of NSE India.

## Getting Started

[NSE India Option Chain](https://www.nseindia.com/option-chain) is a free to use data that tracks prices for the expiry of any
boarder index (like `NIFTY`, `BANKNIFTY`, etc.) and also option chain information of any stock available for trading in the
exchanges (NSE/BSE). The module uses the NSE India API that returns the data as a JSON object and transforms (cleaning, analysis)
the data to be represented as a table (dataframe) or dump the data into an MS Excel file.

```python
pip install nseoptions # yet to be published

import nseoptions
import datetime as dt

response, data, metrics = nseoptions.core.NSEOptionChain(symbol = "NIFTY", expiry = dt.date(2027, 2, 27))
data.sample(3)
```

We recommend that you store the JSON response as is in a MongoDB like NoSQL database, and you can also store the parsed
dataframe into a simple SQL database.

</div>

## Web Dashboard

<div align = "justify">

A modern, production-grade **ReactJS dashboard** (FastAPI backend) ships under
`nseoptions/dashboard/`. It turns the live NSE option chain into four tools:

- **Option Chain** &mdash; a Sensibull-style live heatmap (CALLS | STRIKE | PUTS, mirrored)
  modelled on the Excel template, with the %&#8209;change&#8209;in&#8209;OI colour scale
  (red `#F8696B` &rarr; yellow `#FFEB84` &rarr; green `#63BE7B`), OI walls, a PCR gauge,
  max&#8209;pain and the IV smile.
- **History** &mdash; per&#8209;strike price / OI / IV time series, persisted to SQLite.
- **Strategy Builder** &mdash; a multi&#8209;leg payoff analyzer (breakevens, max P/L, net greeks).
- **Suggestions** &mdash; rules&#8209;based strategy ideas from the current scenario
  (PCR, IV regime, days&#8209;to&#8209;expiry, max&#8209;pain gap).

The backend runs a single NSE poller, caches the chain in memory and fans live
updates out to every client over a WebSocket; it consumes the `nseoptions` public
API only and never modifies the data module.

</div>

```bash
# 1. backend dependencies (kept separate from the core requirements)
pip install -r requirements-dashboard.txt

# 2. build the React bundle (served by the backend); needs Node 18+
cd nseoptions/dashboard/frontend && npm install && npm run build && cd -

# 3. launch the dashboard -> http://127.0.0.1:8000
python dashboard.py --symbol NIFTY --port 8000
```

`python dashboard.py --help` lists every option (`--symbol`, `--expiry`, `--port`,
`--interval`, `--nstrikes`, `--no-verify`, `--dev`). In `--dev` mode the backend
enables CORS for the Vite dev server (`npm run dev` on `:5173`) for hot reloading.

> [!NOTE]
> The dashboard is read-only market analytics &mdash; it places no orders. Greeks are
> computed locally (Black-Scholes) from the NSE implied volatility.

> [!NOTE]
> MS Excel associated with the project is a premium version [more details](#). Please request for the MS Excel file [here](#).

---

<div align = "center">

![UNLICENSE File](https://img.shields.io/github/license/iTraders/nseoptions?style=plastic)
[![DISCLAIMER File](https://img.shields.io/badge/⚠-DISCLAIMER-yellow?style=plastic)](https://github.com/iTraders/nseoptions/blob/master/DISCLAIMER.md)

</div>

<div align = "justify">

The code is provided 'as is' and is intended solely for informational purposes. The developers of this project disclaim any
responsibility for any profit or loss incurred as a result of using this code.

</div>
