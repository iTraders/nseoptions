# -*- encoding: utf-8 -*-

"""
Rules-Based Strategy Suggester (Pluggable Provider)

Turns the current option chain scenario into a ranked list of explainable
option strategies. A :class:`MarketContext` distils the chain + analytics
(PCR, ATM IV regime, days-to-expiry, max-pain gap, directional bias) and a
:class:`SuggestionProvider` maps that context to concrete, defined-risk
strategies with a plain-language rationale.

The provider is deliberately an abstract interface: today a deterministic
:class:`RulesBasedSuggester` is shipped, but a future ``ClaudeSuggester``
can implement the same :meth:`SuggestionProvider.suggest` contract and be
swapped in via settings with no change to the service or the server.

@author:  Debmalya Pramanik
@version: v0.0.1
@copywright: 2024; Debmalya Pramanik
"""

import abc
import datetime as dt

from dataclasses import dataclass

from nseoptions.dashboard import schemas, analytics


@dataclass
class MarketContext:
    """Distilled market scenario that drives the strategy suggestions."""

    symbol      : str
    expiry      : str
    spot        : float
    atm         : float
    multiple    : int
    pcr         : float
    atm_iv      : float
    iv_regime   : str  # one of "low" / "normal" / "high"
    bias        : str  # one of "bullish" / "bearish" / "neutral"
    dte         : int
    max_pain    : float | None
    maxpain_gap : float
    lot_size    : int
    rate        : float
    quotes      : dict
    now         : dt.datetime | None = None # "as-of" anchor (None -> live clock)

    def summary(self) -> dict:
        """A compact, JSON-friendly view (drops the heavy quote lookup)."""

        return {
            "pcr"         : round(self.pcr, 3),
            "atm_iv"      : self.atm_iv,
            "iv_regime"   : self.iv_regime,
            "bias"        : self.bias,
            "dte"         : self.dte,
            "spot"        : self.spot,
            "atm"         : self.atm,
            "max_pain"    : self.max_pain,
            "maxpain_gap" : self.maxpain_gap,
            "lot_size"    : self.lot_size
        }


def build_context(
    chain : schemas.ChainOut, analytic : schemas.AnalyticsOut,
    rate : float = 0.065, now : dt.datetime | None = None
) -> MarketContext:
    """Assemble a :class:`MarketContext` from a chain + its analytics."""

    quotes = analytics.quote_lookup(chain)

    # ? at-the-money implied volatility -> the volatility regime proxy
    atm_iv = 0.0
    for row in chain.rows:
        if row.is_atm:
            legs = [
                row.ce.impliedVolatility if row.ce else 0.0,
                row.pe.impliedVolatility if row.pe else 0.0
            ]
            legs = [iv for iv in legs if iv]
            atm_iv = sum(legs) / len(legs) if legs else 0.0
            break

    iv_regime = "low" if (atm_iv and atm_iv < 13.0) else ("high" if atm_iv > 20.0 else "normal")

    pcr  = chain.put_call_ratio
    bias = "bullish" if pcr >= 1.2 else ("bearish" if 0.0 < pcr <= 0.8 else "neutral")
    dte  = max(int(round(analytics.years_to_expiry(chain.expiry, now) * 365.0)), 0)

    gap = (chain.underlying - analytic.max_pain) if analytic.max_pain else 0.0

    return MarketContext(
        symbol = chain.symbol, expiry = chain.expiry, spot = chain.underlying,
        atm = chain.atm, multiple = chain.multiple, pcr = pcr,
        atm_iv = round(atm_iv, 2), iv_regime = iv_regime, bias = bias, dte = dte,
        max_pain = analytic.max_pain, maxpain_gap = round(gap, 2),
        lot_size = analytics.lot_size(chain.symbol), rate = rate,
        quotes = quotes, now = now
    )


class SuggestionProvider(abc.ABC):
    """Pluggable strategy-suggestion provider interface."""

    @abc.abstractmethod
    def suggest(self, context : MarketContext) -> list:
        """Return a ranked list of :class:`schemas.Suggestion` for a context."""

        raise NotImplementedError


class RulesBasedSuggester(SuggestionProvider):
    """
    Deterministic, Explainable Strategy Suggester

    Maps the market regime (directional bias from PCR, the ATM IV regime,
    days-to-expiry and the max-pain gap) to a ranked list of defined-risk
    option strategies, each carrying the conditions that fired as its
    rationale. No external/AI dependency.
    """

    def __init__(self, max_results : int = 4) -> None:
        self.max_results = max_results


    def suggest(self, context : MarketContext) -> list:
        ctx = context

        # ! no live open-interest (market likely closed) -> informational only
        if ctx.max_pain is None and ctx.pcr == 0.0:
            return [schemas.Suggestion(
                name = "No Live Signal", bias = "neutral", legs = [],
                rationale = ["No live open interest - the market may be closed."],
                score = 0.0
            )]

        common = [
            f"PCR {ctx.pcr:.2f}",
            f"ATM IV {ctx.atm_iv:.1f}% ({ctx.iv_regime})",
            f"{ctx.dte} day(s) to expiry"
        ]
        if ctx.max_pain:
            rel = "above" if ctx.maxpain_gap > 0 else "below"
            common.append(f"spot {rel} max-pain {ctx.max_pain:.0f}")

        out : list = []

        if ctx.bias == "bullish":
            lead = f"PCR {ctx.pcr:.2f} >= 1.20 -> put writers dominate (bullish)"
            if ctx.iv_regime in ("low", "normal"):
                out.append(self._bull_call_spread(
                    ctx, 0.78, [lead, "low/normal IV favours a debit spread"] + common))
            if ctx.iv_regime in ("high", "normal"):
                out.append(self._bull_put_spread(
                    ctx, 0.72, [lead, "elevated IV favours selling premium (credit spread)"] + common))
        elif ctx.bias == "bearish":
            lead = f"PCR {ctx.pcr:.2f} <= 0.80 -> call writers dominate (bearish)"
            if ctx.iv_regime in ("low", "normal"):
                out.append(self._bear_put_spread(
                    ctx, 0.78, [lead, "low/normal IV favours a debit spread"] + common))
            if ctx.iv_regime in ("high", "normal"):
                out.append(self._bear_call_spread(
                    ctx, 0.72, [lead, "elevated IV favours selling premium (credit spread)"] + common))
        else:
            lead = f"PCR {ctx.pcr:.2f} in 0.80-1.20 -> range-bound bias"
            if ctx.iv_regime == "high" or ctx.dte <= 7:
                out.append(self._iron_condor(
                    ctx, 0.74, [lead, "high IV / short DTE favours a defined-risk iron condor"] + common))
            if ctx.iv_regime == "high" and ctx.dte <= 3:
                out.append(self._short_straddle(
                    ctx, 0.60, [lead, "very high IV near expiry -> short straddle (advanced, undefined risk)"] + common))
            if ctx.iv_regime == "low":
                out.append(self._long_straddle(
                    ctx, 0.66, [lead, "low IV -> long straddle to position for a volatility expansion"] + common))
                out.append(self._long_strangle(
                    ctx, 0.58, [lead, "low IV -> a cheaper long strangle for a breakout"] + common))

        if not out:
            out.append(self._iron_condor(
                ctx, 0.50, ["no strong directional signal -> neutral defined-risk condor"] + common))

        # ? a gentle mean-reversion nudge when spot is far from max-pain
        if ctx.max_pain and abs(ctx.maxpain_gap) > 2 * ctx.multiple:
            drift = "down" if ctx.maxpain_gap > 0 else "up"
            for suggestion in out:
                suggestion.rationale.append(
                    f"spot is far from max-pain {ctx.max_pain:.0f}; a drift {drift} toward it is likely")

        # ? attach the realised payoff metrics and rank by descending score
        for suggestion in out:
            self._attach_payoff(ctx, suggestion)

        out.sort(key = lambda s : s.score, reverse = True)
        return out[:self.max_results]


    # -------- strike selection + strategy builders -------- #

    def _strike(self, ctx : MarketContext, target : float, leg : str) -> float:
        """Snap a target strike to the nearest one actually quoted."""

        available = sorted({strike for (strike, kind) in ctx.quotes if kind == leg})
        if not available:
            return target
        return min(available, key = lambda strike : abs(strike - target))


    def _leg(self, ctx : MarketContext, steps : int, leg : str, side : str) -> schemas.StrategyLeg:
        """Build one strategy leg ``steps`` strike-multiples from the ATM."""

        target = ctx.atm + steps * ctx.multiple
        return schemas.StrategyLeg(
            strike = self._strike(ctx, target, leg), leg = leg, side = side, qty = 1
        )


    @staticmethod
    def _clamp(score : float) -> float:
        return round(max(0.0, min(score, 1.0)), 3)


    def _bull_call_spread(self, ctx, score, rationale) -> schemas.Suggestion:
        legs = [self._leg(ctx, 0, "CE", "BUY"), self._leg(ctx, 2, "CE", "SELL")]
        return schemas.Suggestion(name = "Bull Call Spread", bias = "bullish", legs = legs, rationale = rationale, score = self._clamp(score))

    def _bull_put_spread(self, ctx, score, rationale) -> schemas.Suggestion:
        legs = [self._leg(ctx, 0, "PE", "SELL"), self._leg(ctx, -2, "PE", "BUY")]
        return schemas.Suggestion(name = "Bull Put Spread", bias = "bullish", legs = legs, rationale = rationale, score = self._clamp(score))

    def _bear_put_spread(self, ctx, score, rationale) -> schemas.Suggestion:
        legs = [self._leg(ctx, 0, "PE", "BUY"), self._leg(ctx, -2, "PE", "SELL")]
        return schemas.Suggestion(name = "Bear Put Spread", bias = "bearish", legs = legs, rationale = rationale, score = self._clamp(score))

    def _bear_call_spread(self, ctx, score, rationale) -> schemas.Suggestion:
        legs = [self._leg(ctx, 0, "CE", "SELL"), self._leg(ctx, 2, "CE", "BUY")]
        return schemas.Suggestion(name = "Bear Call Spread", bias = "bearish", legs = legs, rationale = rationale, score = self._clamp(score))

    def _iron_condor(self, ctx, score, rationale) -> schemas.Suggestion:
        legs = [
            self._leg(ctx, 2, "CE", "SELL"), self._leg(ctx, 4, "CE", "BUY"),
            self._leg(ctx, -2, "PE", "SELL"), self._leg(ctx, -4, "PE", "BUY")
        ]
        return schemas.Suggestion(name = "Iron Condor", bias = "neutral", legs = legs, rationale = rationale, score = self._clamp(score))

    def _short_straddle(self, ctx, score, rationale) -> schemas.Suggestion:
        legs = [self._leg(ctx, 0, "CE", "SELL"), self._leg(ctx, 0, "PE", "SELL")]
        return schemas.Suggestion(name = "Short Straddle", bias = "neutral", legs = legs, rationale = rationale, score = self._clamp(score))

    def _long_straddle(self, ctx, score, rationale) -> schemas.Suggestion:
        legs = [self._leg(ctx, 0, "CE", "BUY"), self._leg(ctx, 0, "PE", "BUY")]
        return schemas.Suggestion(name = "Long Straddle", bias = "volatile", legs = legs, rationale = rationale, score = self._clamp(score))

    def _long_strangle(self, ctx, score, rationale) -> schemas.Suggestion:
        legs = [self._leg(ctx, 2, "CE", "BUY"), self._leg(ctx, -2, "PE", "BUY")]
        return schemas.Suggestion(name = "Long Strangle", bias = "volatile", legs = legs, rationale = rationale, score = self._clamp(score))


    def _attach_payoff(self, ctx : MarketContext, suggestion : schemas.Suggestion) -> None:
        """Run the payoff engine to fill in max P/L and breakevens."""

        if not suggestion.legs:
            return

        result = analytics.payoff(
            suggestion.legs, ctx.spot, ctx.expiry,
            lot_size = ctx.lot_size, rate = ctx.rate, quotes = ctx.quotes, now = ctx.now
        )
        suggestion.max_profit = result.max_profit
        suggestion.max_loss   = result.max_loss
        suggestion.breakevens = result.breakevens
