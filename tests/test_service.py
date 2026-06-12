# -*- encoding: utf-8 -*-

"""Tests for the option chain assembly + cache (offline, fixture-driven)."""

from nseoptions.dashboard import service


def test_assemble_chain_rows(sample, expiry):
    chain = service.assemble_chain(sample, "NIFTY", expiry, nstrikes = 20)

    assert chain.symbol == "NIFTY"
    assert chain.expiry == expiry
    assert chain.atm == 23450.0
    assert chain.multiple == 50
    assert len(chain.rows) == 41            # 2 * nstrikes + 1
    assert sum(1 for row in chain.rows if row.is_atm) == 1
    assert chain.put_call_ratio > 1.0       # the fixture is put-heavy


def test_multi_expiry_from_one_response(sample):
    chain = service.assemble_chain(sample, "NIFTY", "31-Jul-2025", nstrikes = 10)

    assert chain.expiry == "31-Jul-2025"
    assert len(chain.rows) == 21


def test_resolve_expiry_defaults_to_nearest(sample):
    assert service.assemble_chain(sample, "NIFTY", None, 20).expiry == "26-Jun-2025"
    assert service.assemble_chain(sample, "NIFTY", "bogus", 20).expiry == "26-Jun-2025"


def test_degraded_zero_oi_path(closed, expiry):
    chain = service.assemble_chain(closed, "NIFTY", expiry, nstrikes = 15)

    assert chain.put_call_ratio == 0.0      # guarded division, no raise
    assert chain.tot_oi_ce == 0.0
    assert len(chain.rows) > 0
