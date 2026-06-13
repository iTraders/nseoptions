# -*- encoding: utf-8 -*-

"""
Option Chain Analytics - Greeks, Max-Pain, OI Walls and Payoff

Pure, side-effect-free analytics derived from the cached option chain.
None of this lives in the locked data module; the functions here consume
the raw NSE records (full chain) and the processed :class:`schemas.ChainOut`
to produce the derived metrics the dashboard renders:

    * Black-Scholes price + greeks (via :func:`math.erf`, no scipy)
    * max-pain and the per-strike writer-loss curve
    * support/resistance open-interest walls and the IV smile
    * the expiry payoff curve for an arbitrary multi-leg strategy

@author:  Debmalya Pramanik
@version: v0.0.1
@copywright: 2024; Debmalya Pramanik
"""

import math
import datetime as dt

from nseoptions.dashboard import schemas

# ? indian index/stock lot sizes (approximate, time-varying defaults); the
# ? payoff SHAPE/breakevens are lot-size invariant, only magnitude scales
LOT_SIZES = {
    "NIFTY"      : 75,
    "BANKNIFTY"  : 35,
    "FINNIFTY"   : 65,
    "MIDCPNIFTY" : 140,
    "NIFTYNXT50" : 120,
    "SENSEX"     : 20,
    "BANKEX"     : 30
}

IST       = dt.timezone(dt.timedelta(hours = 5, minutes = 30))
SQRT_2    = math.sqrt(2.0)
SQRT_2PI  = math.sqrt(2.0 * math.pi)
_TOL      = 1e-6


def lot_size(symbol : str) -> int:
    """Return the contract lot size for a symbol (defaults to 1)."""

    return LOT_SIZES.get(symbol.upper(), 1)


def _pdf(x : float) -> float:
    """Standard normal probability density function."""

    return math.exp(-0.5 * x * x) / SQRT_2PI


def _cdf(x : float) -> float:
    """Standard normal cumulative distribution function (via ``erf``)."""

    return 0.5 * (1.0 + math.erf(x / SQRT_2))


def years_to_expiry(expiry : str, now : dt.datetime | None = None) -> float:
    """
    Year-fraction from ``now`` to the expiry settlement (15:30 IST).

    Clamped to a tiny positive epsilon so the greeks never divide by zero
    on (or after) expiry day.
    """

    settle = dt.datetime.strptime(expiry, "%d-%b-%Y").replace(
        hour = 15, minute = 30, tzinfo = IST
    )

    now = now or dt.datetime.now(IST)
    if now.tzinfo is None:
        now = now.replace(tzinfo = IST)

    seconds = (settle - now).total_seconds()
    return max(seconds / (365.0 * 24.0 * 3600.0), _TOL)


def black_scholes_price(
    spot : float, strike : float, t : float, iv : float,
    rate : float = 0.065, kind : str = "CE"
) -> float:
    """Black-Scholes fair value of a European option (``iv`` in percent)."""

    sigma = iv / 100.0
    if t <= 0 or sigma <= 0 or spot <= 0 or strike <= 0:
        # ! degenerate -> collapse to intrinsic value
        return max(spot - strike, 0.0) if kind == "CE" else max(strike - spot, 0.0)

    sqrt_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    disc = math.exp(-rate * t)

    if kind == "CE":
        return spot * _cdf(d1) - strike * disc * _cdf(d2)
    return strike * disc * _cdf(-d2) - spot * _cdf(-d1)


def black_scholes_greeks(
    spot : float, strike : float, t : float, iv : float,
    rate : float = 0.065, kind : str = "CE"
) -> schemas.Greeks:
    """
    Black-Scholes greeks for a single option leg.

    ``vega`` is per 1% change in volatility, ``theta`` is per calendar day.
    A missing/zero IV or an expired contract yields an intrinsic-sign delta
    with the remaining greeks zeroed and ``iv_missing`` flagged.
    """

    sigma = iv / 100.0
    if t <= 0 or sigma <= 0 or spot <= 0 or strike <= 0:
        if kind == "CE":
            delta = 1.0 if spot > strike else 0.0
        else:
            delta = -1.0 if spot < strike else 0.0
        return schemas.Greeks(delta = delta, iv_missing = sigma <= 0)

    sqrt_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    disc = math.exp(-rate * t)

    gamma = _pdf(d1) / (spot * sigma * sqrt_t)
    vega  = spot * _pdf(d1) * sqrt_t / 100.0

    if kind == "CE":
        delta = _cdf(d1)
        theta = (-spot * _pdf(d1) * sigma / (2.0 * sqrt_t) - rate * strike * disc * _cdf(d2)) / 365.0
        rho   = strike * t * disc * _cdf(d2) / 100.0
    else:
        delta = _cdf(d1) - 1.0
        theta = (-spot * _pdf(d1) * sigma / (2.0 * sqrt_t) + rate * strike * disc * _cdf(-d2)) / 365.0
        rho   = -strike * t * disc * _cdf(-d2) / 100.0

    return schemas.Greeks(
        delta = round(delta, 6), gamma = round(gamma, 8),
        theta = round(theta, 4), vega = round(vega, 4), rho = round(rho, 4)
    )


def _legs_for_expiry(response : dict, expiry : str) -> list:
    """Yield the raw ``records.data`` items for a single expiry."""

    return [
        item for item in response.get("records", {}).get("data", [])
        if item.get("expiryDate") == expiry
    ]


def _oi(item : dict, side : str) -> float:
    """Open interest of one leg of a raw record (``0.0`` if absent)."""

    return float(item.get(side, {}).get("openInterest") or 0.0)


def max_pain(response : dict, expiry : str) -> tuple:
    """
    Compute max-pain over every strike of an expiry.

    :rtype: tuple
    :return: ``(max_pain_strike, [StrikeLoss, ...])`` where the loss is the
        aggregate option-writer pain at each candidate settlement price.
        Returns ``(None, [])`` when there is no open interest.
    """

    items   = _legs_for_expiry(response, expiry)
    ce_oi   = {float(i["strikePrice"]) : _oi(i, "CE") for i in items}
    pe_oi   = {float(i["strikePrice"]) : _oi(i, "PE") for i in items}
    strikes = sorted(set(ce_oi) | set(pe_oi)) # ! union so PE-only strikes count

    if not strikes or (sum(ce_oi.values()) + sum(pe_oi.values())) == 0:
        return None, []

    losses = []
    for settle in strikes:
        loss = (
            sum(ce_oi.get(k, 0.0) * max(settle - k, 0.0) for k in strikes)
            + sum(pe_oi.get(k, 0.0) * max(k - settle, 0.0) for k in strikes)
        )
        losses.append(schemas.StrikeLoss(strikePrice = settle, loss = round(loss, 2)))

    pain = min(losses, key = lambda point : point.loss).strikePrice
    return pain, losses


def oi_walls(response : dict, expiry : str, top : int = 3) -> tuple:
    """
    Identify the support (PE OI) and resistance (CE OI) walls.

    :rtype: tuple
    :return: ``(support, resistance)`` lists of :class:`schemas.WallPoint`,
        each sorted by descending open interest (largest wall first).
    """

    calls, puts = [], []
    for item in _legs_for_expiry(response, expiry):
        strike = float(item["strikePrice"])
        if "CE" in item:
            calls.append(schemas.WallPoint(
                strikePrice = strike,
                openInterest = _oi(item, "CE"),
                changeinOpenInterest = float(item["CE"].get("changeinOpenInterest") or 0.0)
            ))
        if "PE" in item:
            puts.append(schemas.WallPoint(
                strikePrice = strike,
                openInterest = _oi(item, "PE"),
                changeinOpenInterest = float(item["PE"].get("changeinOpenInterest") or 0.0)
            ))

    resistance = sorted(calls, key = lambda w : w.openInterest, reverse = True)[:top]
    support    = sorted(puts,  key = lambda w : w.openInterest, reverse = True)[:top]
    return support, resistance


def iv_smile(response : dict, expiry : str) -> list:
    """Return the per-strike CE/PE implied-volatility smile, sorted by strike."""

    points = []
    for item in sorted(_legs_for_expiry(response, expiry), key = lambda i : float(i["strikePrice"])):
        points.append(schemas.IVPoint(
            strikePrice = float(item["strikePrice"]),
            ce_iv = float(item.get("CE", {}).get("impliedVolatility") or 0.0),
            pe_iv = float(item.get("PE", {}).get("impliedVolatility") or 0.0)
        ))
    return points


def build_analytics(
    response : dict, symbol : str, expiry : str, underlying : float
) -> schemas.AnalyticsOut:
    """Assemble the derived :class:`schemas.AnalyticsOut` for one expiry."""

    pain, losses = max_pain(response, expiry)
    support, resistance = oi_walls(response, expiry)
    smile = iv_smile(response, expiry)

    return schemas.AnalyticsOut(
        symbol = symbol, expiry = expiry, underlying = underlying,
        max_pain = pain, loss_by_strike = losses,
        support = support, resistance = resistance,
        iv_smile = smile, no_data = pain is None
    )


def quote_lookup(chain : schemas.ChainOut) -> dict:
    """Build a ``(strike, leg) -> LegQuote`` lookup from a processed chain."""

    table : dict = {}
    for row in chain.rows:
        if row.ce is not None:
            table[(row.strikePrice, "CE")] = row.ce
        if row.pe is not None:
            table[(row.strikePrice, "PE")] = row.pe
    return table


def _leg_payoff(leg : schemas.StrategyLeg, premium : float, multiplier : float, spot : float) -> float:
    """Per-leg profit/loss at an expiry settlement price ``spot``."""

    if leg.leg == "CE":
        intrinsic = max(spot - leg.strike, 0.0)
    else:
        intrinsic = max(leg.strike - spot, 0.0)

    sign = 1.0 if leg.side == "BUY" else -1.0
    return sign * (intrinsic - premium) * multiplier


def payoff(
    legs       : list,
    spot       : float,
    expiry     : str,
    lot_size   : int = 1,
    lots       : int = 1,
    rate       : float = 0.065,
    quotes     : dict | None = None,
    points     : int = 200,
    now        : dt.datetime | None = None
) -> schemas.PayoffOut:
    """
    Compute the expiry payoff curve and headline metrics of a strategy.

    Premiums default to the leg's live LTP (from ``quotes``) when not
    explicitly supplied. Exact max-profit/-loss and breakevens are derived
    from the piecewise-linear kink analysis (extrema at 0, the strikes, or
    the unbounded tail); the rendered curve is sampled on a price grid.
    """

    quotes = quotes or {}

    if not legs:
        return schemas.PayoffOut(spot = round(spot, 2))

    estimated  = False
    premiums   = []
    for leg in legs:
        price = leg.price
        if price is None:
            quote = quotes.get((leg.strike, leg.leg))
            price = quote.lastPrice if quote else 0.0
            estimated = True
        premiums.append(price)

    multipliers = [leg.qty * lots * lot_size for leg in legs]

    def total(price : float) -> float:
        return sum(
            _leg_payoff(leg, prem, mult, price)
            for leg, prem, mult in zip(legs, premiums, multipliers)
        )

    # ? sampled display curve over a practical price band around the legs
    strikes = sorted({leg.strike for leg in legs})
    lo = 0.9 * min(strikes[0], spot)
    hi = 1.1 * max(strikes[-1], spot)
    grid = [lo + (hi - lo) * i / (points - 1) for i in range(points)]
    curve = [schemas.PayoffPoint(spot = round(s, 2), pnl = round(total(s), 2)) for s in grid]

    # ? exact metrics: payoff is piecewise-linear, extrema live at the kinks
    far   = strikes[-1] * 2.0 + spot
    nodes = [0.0] + strikes + [far]
    vals  = [total(s) for s in nodes]

    real_vals  = vals[:-1] # exclude the synthetic far node from extrema
    max_profit = round(max(real_vals), 2)
    max_loss   = round(min(real_vals), 2)

    slope_right = total(far) - total(far - 1.0)
    if slope_right > _TOL:
        max_profit = None # unbounded upside (e.g. naked long/short structures)
    elif slope_right < -_TOL:
        max_loss = None   # unbounded downside (e.g. naked short call)

    breakevens = []
    for i in range(1, len(nodes)):
        y0, y1 = vals[i - 1], vals[i]
        x0, x1 = nodes[i - 1], nodes[i]
        if y0 == 0.0 and 0.0 < x0:
            breakevens.append(round(x0, 2))
        elif (y0 < 0.0) != (y1 < 0.0) and y1 != y0:
            breakevens.append(round(x0 - y0 * (x1 - x0) / (y1 - y0), 2))
    breakevens = sorted({be for be in breakevens if be > 0})

    # ? net position greeks at the current spot using each leg's live IV
    net = schemas.Greeks()
    t = years_to_expiry(expiry, now)
    for leg, mult in zip(legs, multipliers):
        quote = quotes.get((leg.strike, leg.leg))
        iv = quote.impliedVolatility if quote else 0.0
        greeks = black_scholes_greeks(spot, leg.strike, t, iv, rate, leg.leg)
        sign = 1.0 if leg.side == "BUY" else -1.0
        net.delta += greeks.delta * sign * mult
        net.gamma += greeks.gamma * sign * mult
        net.theta += greeks.theta * sign * mult
        net.vega  += greeks.vega * sign * mult
        net.rho   += greeks.rho * sign * mult
        net.iv_missing = net.iv_missing or greeks.iv_missing

    net.delta = round(net.delta, 4)
    net.gamma = round(net.gamma, 6)
    net.theta = round(net.theta, 4)
    net.vega  = round(net.vega, 4)
    net.rho   = round(net.rho, 4)

    return schemas.PayoffOut(
        spot = round(spot, 2), lot_size = lot_size, curve = curve,
        breakevens = breakevens, max_profit = max_profit, max_loss = max_loss,
        net_greeks = net, estimated = estimated
    )
