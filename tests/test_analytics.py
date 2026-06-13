# -*- encoding: utf-8 -*-

"""Tests for the analytics engine: greeks, max-pain, walls and payoff."""

import math

from nseoptions.dashboard import service, analytics, schemas


def test_put_call_parity(asof, expiry):
    t = analytics.years_to_expiry(expiry, now = asof)
    call = analytics.black_scholes_price(23456.75, 23450.0, t, 14.0, 0.065, "CE")
    put  = analytics.black_scholes_price(23456.75, 23450.0, t, 14.0, 0.065, "PE")

    parity = 23456.75 - 23450.0 * math.exp(-0.065 * t)
    assert abs((call - put) - parity) < 1e-6


def test_atm_greeks_in_range(asof, expiry):
    t = analytics.years_to_expiry(expiry, now = asof)

    call = analytics.black_scholes_greeks(23456.75, 23450.0, t, 14.0, 0.065, "CE")
    assert 0.45 < call.delta < 0.65 and call.gamma > 0 and call.vega > 0 and call.theta < 0

    put = analytics.black_scholes_greeks(23456.75, 23450.0, t, 14.0, 0.065, "PE")
    assert -0.65 < put.delta < -0.35


def test_greeks_missing_iv_flagged():
    greeks = analytics.black_scholes_greeks(100.0, 100.0, 0.1, 0.0, kind = "CE")
    assert greeks.iv_missing and greeks.gamma == 0.0


def test_max_pain_minimizes_writer_loss(sample, expiry):
    pain, losses = analytics.max_pain(sample, expiry)

    assert pain == 23500.0 and losses
    assert min(losses, key = lambda point : point.loss).strikePrice == pain


def test_max_pain_includes_pe_only_strikes():
    # a strike quoted only on the PE side must still be a candidate + counted
    response = {
        "records": {
            "data": [
                {"strikePrice": 100, "expiryDate": "26-Jun-2025", "CE": {"openInterest": 0}, "PE": {"openInterest": 1000}},
                {"strikePrice": 110, "expiryDate": "26-Jun-2025", "PE": {"openInterest": 5000}},
                {"strikePrice": 120, "expiryDate": "26-Jun-2025", "CE": {"openInterest": 1000}},
            ]
        }
    }
    pain, losses = analytics.max_pain(response, "26-Jun-2025")
    assert pain is not None
    assert 110.0 in {point.strikePrice for point in losses}


def test_oi_walls_support_below_resistance_above(sample, expiry):
    support, resistance = analytics.oi_walls(sample, expiry)

    assert support and resistance
    assert support[0].strikePrice < 23456.75      # put wall = support, below spot
    assert resistance[0].strikePrice > 23456.75   # call wall = resistance, above spot


def test_payoff_long_call(sample, asof, expiry):
    chain = service.assemble_chain(sample, "NIFTY", expiry, nstrikes = 20)
    leg   = [schemas.StrategyLeg(strike = 23450, leg = "CE", side = "BUY", price = 100.0)]

    result = analytics.payoff(
        leg, chain.underlying, expiry, lot_size = 75,
        quotes = analytics.quote_lookup(chain), now = asof
    )

    assert result.max_loss == -7500.0           # premium * lot
    assert result.max_profit is None            # unbounded upside
    assert result.breakevens == [23550.0]       # strike + premium


def test_payoff_spread_is_defined_risk(sample, asof, expiry):
    chain = service.assemble_chain(sample, "NIFTY", expiry, nstrikes = 20)
    legs  = [
        schemas.StrategyLeg(strike = 23450, leg = "CE", side = "BUY"),
        schemas.StrategyLeg(strike = 23550, leg = "CE", side = "SELL")
    ]

    result = analytics.payoff(
        legs, chain.underlying, expiry, lot_size = 75,
        quotes = analytics.quote_lookup(chain), now = asof
    )

    assert result.max_profit is not None and result.max_loss is not None
    assert result.estimated is True             # premiums inferred from LTP
