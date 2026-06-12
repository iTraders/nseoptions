# -*- encoding: utf-8 -*-

"""
Offline NSE Option-Chain Fixture Generator

Produces deterministic, schema-faithful NSE option-chain JSON payloads
so the dashboard test-suite can run fully offline and never touch the
live NSE feed. The generated structure mirrors the real NSE response
(``records.data[].{CE,PE}`` + ``filtered``) consumed by the locked
:class:`nseoptions.processing.OptionChainProcessing`.

Run once (or whenever the fixtures need refreshing):

    python tests/fixtures/_generate_fixtures.py

@author:  Debmalya Pramanik
@version: v0.0.1
@copywright: 2024; Debmalya Pramanik
"""

import os
import json
import math
import random
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))

# ? a fixed reference snapshot so the fixtures are byte-stable on re-run
ASOF      = dt.datetime(2025, 6, 13, 15, 30, 0)
SYMBOL    = "NIFTY"
SPOT      = 23456.75
MULTIPLE  = 50
NSTEPS    = 30 # strikes either side of the ATM (61 strikes total)
EXPIRIES  = ["26-Jun-2025", "03-Jul-2025", "31-Jul-2025"]


def _round(value : float, ndigits : int = 2) -> float:
    return round(float(value), ndigits)


def _leg(strike : float, atm : float, expiry : str, kind : str, dte : int, zero : bool) -> dict:
    """Build one realistic CE/PE leg for a strike at a given expiry."""

    off = (strike - atm) / MULTIPLE # signed steps away from the ATM

    intrinsic = max(SPOT - strike, 0.0) if kind == "CE" else max(strike - SPOT, 0.0)
    tnorm     = math.sqrt(max(dte, 1) / 30.0) # longer expiry -> more time value
    tvalue    = 95.0 * math.exp(-(off ** 2) / 70.0) * tnorm
    ltp       = _round(intrinsic + tvalue)

    # ? a simple volatility smile: lowest near the ATM, rising on the wings
    iv = _round(11.0 + 0.40 * abs(off) + 0.015 * off ** 2)

    # ? open-interest skew: CE walls build above spot, PE walls below it;
    # ? the put side is intentionally heavier so PCR > 1 (mild bullishness)
    if kind == "CE":
        peak, amp = 6.0, 7_200_000
    else:
        peak, amp = -4.0, 9_800_000
    oi = 0 if zero else int(amp * math.exp(-((off - peak) ** 2) / 24.0) + 15_000)

    chg_oi = 0 if zero else int(oi * random.uniform(-0.35, 0.55))
    base   = oi - chg_oi
    pch_oi = _round((chg_oi / base) * 100.0) if base else 0.0
    volume = 0 if zero else int(oi * random.uniform(0.15, 1.4))

    chg   = _round(ltp * random.uniform(-0.18, 0.18))
    base  = ltp - chg
    pch   = _round((chg / base) * 100.0) if base else 0.0

    spread = max(_round(ltp * 0.01), 0.05)
    bid    = _round(max(ltp - spread, 0.05))
    ask    = _round(ltp + spread)

    return {
        "strikePrice"           : strike,
        "expiryDate"            : expiry,
        "underlying"            : SYMBOL,
        "identifier"            : f"OPTIDX{SYMBOL}{expiry}{kind}{int(strike)}",
        "openInterest"          : oi,
        "changeinOpenInterest"  : chg_oi,
        "pchangeinOpenInterest" : pch_oi,
        "totalTradedVolume"     : volume,
        "impliedVolatility"     : 0.0 if zero else iv,
        "lastPrice"             : ltp,
        "change"                : 0.0 if zero else chg,
        "pChange"               : 0.0 if zero else pch,
        "totalBuyQuantity"      : 0 if zero else int(random.uniform(1, 50)) * 75,
        "totalSellQuantity"     : 0 if zero else int(random.uniform(1, 50)) * 75,
        "bidQty"                : 0 if zero else int(random.uniform(1, 40)) * 75,
        "bidprice"              : 0.0 if zero else bid,
        "askQty"                : 0 if zero else int(random.uniform(1, 40)) * 75,
        "askPrice"              : 0.0 if zero else ask,
        "underlyingValue"       : SPOT
    }


def build(zero : bool = False) -> dict:
    """Assemble a complete NSE option-chain response payload."""

    random.seed(42) # ! deterministic output across regenerations

    atm     = round(SPOT / MULTIPLE) * MULTIPLE
    strikes = [atm + step * MULTIPLE for step in range(-NSTEPS, NSTEPS + 1)]

    data : list = []
    for expiry in EXPIRIES:
        dte = (dt.datetime.strptime(expiry, "%d-%b-%Y") - ASOF).days
        for strike in strikes:
            data.append({
                "strikePrice" : strike,
                "expiryDate"  : expiry,
                "PE"          : _leg(strike, atm, expiry, "PE", dte, zero),
                "CE"          : _leg(strike, atm, expiry, "CE", dte, zero)
            })

    # ? the `filtered` block aggregates the front-month (first) expiry
    front  = [item for item in data if item["expiryDate"] == EXPIRIES[0]]
    tot_oi_ce  = sum(item["CE"]["openInterest"] for item in front)
    tot_oi_pe  = sum(item["PE"]["openInterest"] for item in front)
    tot_vol_ce = sum(item["CE"]["totalTradedVolume"] for item in front)
    tot_vol_pe = sum(item["PE"]["totalTradedVolume"] for item in front)

    timestamp = ASOF.strftime("%d-%b-%Y %H:%M:%S")
    return {
        "records" : {
            "expiryDates"     : EXPIRIES,
            "data"            : data,
            "timestamp"       : timestamp,
            "underlyingValue" : SPOT,
            "strikePrices"    : strikes
        },
        "filtered" : {
            "data" : front,
            "CE"   : {"totOI" : tot_oi_ce, "totVol" : tot_vol_ce},
            "PE"   : {"totOI" : tot_oi_pe, "totVol" : tot_vol_pe}
        }
    }


def main() -> None:
    targets = {
        "nse_nifty_sample.json"  : build(zero = False),
        "nse_market_closed.json" : build(zero = True)
    }

    for name, payload in targets.items():
        path = os.path.join(HERE, name)
        with open(path, "w") as f:
            json.dump(payload, f, indent = 2)

        records = payload["records"]
        print(f"  >> wrote {name} : {len(records['data'])} legs, "
              f"PCR(front)={payload['filtered']['PE']['totOI'] / (payload['filtered']['CE']['totOI'] or 1):.3f}")


if __name__ == "__main__":
    main()
