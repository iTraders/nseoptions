# -*- encoding: utf-8 -*-

"""Tests for the rules-based suggester and its pluggable provider interface."""

from nseoptions.dashboard import service, analytics, suggester, schemas


def _context(payload, expiry, asof):
    chain    = service.assemble_chain(payload, "NIFTY", expiry, nstrikes = 20)
    analytic = analytics.build_analytics(payload, "NIFTY", expiry, chain.underlying)
    return suggester.build_context(chain, analytic, now = asof)


def test_bullish_market_suggests_bull_call_spread(sample, asof, expiry):
    context = _context(sample, expiry, asof)
    assert context.bias == "bullish"          # fixture PCR ~ 1.36

    ranked = suggester.RulesBasedSuggester().suggest(context)
    assert ranked and all(s.legs for s in ranked)
    assert "Bull Call Spread" in [s.name for s in ranked]
    assert ranked == sorted(ranked, key = lambda s : s.score, reverse = True)


def test_closed_market_returns_informational(closed, asof, expiry):
    ranked = suggester.RulesBasedSuggester().suggest(_context(closed, expiry, asof))
    assert ranked[0].name == "No Live Signal" and ranked[0].legs == []


def test_provider_is_pluggable(sample, asof, expiry):
    context = _context(sample, expiry, asof)

    class StubSuggester(suggester.SuggestionProvider):
        def suggest(self, ctx):
            return [schemas.Suggestion(name = "Stub", bias = "neutral")]

    # ! a drop-in provider honouring the same ABC contract (future Claude)
    assert StubSuggester().suggest(context)[0].name == "Stub"
