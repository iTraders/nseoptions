# -*- encoding: utf-8 -*-

"""
Pydantic Schemas - the REST/WebSocket Data Contract

The schemas defined here are the single, typed contract shared between
the FastAPI backend and the ReactJS frontend. Every REST response and
WebSocket message is one of these models, which also powers the auto
generated OpenAPI documentation served at ``/docs``.

The leg fields deliberately mirror the column names produced by
:meth:`nseoptions.processing.OptionChainProcessing.makeclean` so the
contract stays faithful to the locked data module.

@author:  Debmalya Pramanik
@version: v0.0.1
@copywright: 2024; Debmalya Pramanik
"""

from typing import Literal

from pydantic import BaseModel

# ! the per-leg numeric fields, in the order makeclean() emits them; the
# ! frontend table consumes the same keys for both the CE and PE legs
# ..versionchanged:: 2026-06-13 NSE v3 Bid/Ask Depth Field Names
LEG_FIELDS = (
    "openInterest",
    "changeinOpenInterest",
    "pchangeinOpenInterest",
    "totalTradedVolume",
    "impliedVolatility",
    "lastPrice",
    "change",
    "pChange",
    "totalBuyQuantity",
    "totalSellQuantity",
    "buyQuantity1",
    "buyPrice1",
    "sellQuantity1",
    "sellPrice1"
)


class LegQuote(BaseModel):
    """A single option leg (CE or PE) quote for one strike price."""

    openInterest          : float = 0.0
    changeinOpenInterest  : float = 0.0
    pchangeinOpenInterest : float = 0.0
    totalTradedVolume     : float = 0.0
    impliedVolatility     : float = 0.0
    lastPrice             : float = 0.0
    change                : float = 0.0
    pChange               : float = 0.0
    totalBuyQuantity      : float = 0.0
    totalSellQuantity     : float = 0.0
    buyQuantity1          : float = 0.0
    buyPrice1             : float = 0.0
    sellQuantity1         : float = 0.0
    sellPrice1            : float = 0.0


class StrikeRow(BaseModel):
    """One option chain row: CALL leg | strike price | PUT leg."""

    strikePrice : float
    ce          : LegQuote | None = None
    pe          : LegQuote | None = None
    is_atm      : bool = False


class Greeks(BaseModel):
    """Black-Scholes option greeks for a single leg or a net position."""

    delta      : float = 0.0
    gamma      : float = 0.0
    theta      : float = 0.0
    vega       : float = 0.0
    rho        : float = 0.0
    iv_missing : bool = False


class ChainOut(BaseModel):
    """The processed option chain snapshot for one symbol and expiry."""

    symbol         : str
    expiry         : str
    underlying     : float
    timestamp      : str
    atm            : float
    multiple       : int
    put_call_ratio : float
    tot_oi_ce      : float
    tot_oi_pe      : float
    tot_vol_ce     : float
    tot_vol_pe     : float
    rows           : list[StrikeRow] = []


class MetaOut(BaseModel):
    """Lightweight metadata: available expiries, status and bounds."""

    symbol     : str
    expiries   : list[str] = []
    expiry     : str | None = None
    multiple   : int | None = None
    nstrikes   : int = 20
    status     : str = "starting"
    detail     : str | None = None
    underlying : float | None = None
    timestamp  : str | None = None


class HealthOut(BaseModel):
    """Liveness probe payload for the dashboard backend."""

    status    : str
    symbol    : str
    last_poll : str | None = None
    clients   : int = 0


class StrikeLoss(BaseModel):
    """Total option-writer loss at a candidate expiry settlement price."""

    strikePrice : float
    loss        : float


class WallPoint(BaseModel):
    """An open-interest wall (support/resistance) at a strike price."""

    strikePrice          : float
    openInterest         : float = 0.0
    changeinOpenInterest : float = 0.0


class IVPoint(BaseModel):
    """The CE/PE implied volatility pair for a strike (the IV smile)."""

    strikePrice : float
    ce_iv       : float = 0.0
    pe_iv       : float = 0.0


class AnalyticsOut(BaseModel):
    """Derived analytics: max-pain, OI walls and the IV smile."""

    symbol         : str
    expiry         : str
    underlying     : float = 0.0
    max_pain       : float | None = None
    loss_by_strike : list[StrikeLoss] = []
    support        : list[WallPoint] = []
    resistance     : list[WallPoint] = []
    iv_smile       : list[IVPoint] = []
    no_data        : bool = False


class StrategyLeg(BaseModel):
    """A single leg of a user-built (or suggested) option strategy."""

    strike : float
    leg    : Literal["CE", "PE"]
    side   : Literal["BUY", "SELL"]
    qty    : int = 1
    price  : float | None = None # premium override; falls back to LTP


class PayoffIn(BaseModel):
    """Request body for the multi-leg strategy payoff analyzer."""

    symbol : str
    expiry : str
    lots   : int = 1
    legs   : list[StrategyLeg]


class PayoffPoint(BaseModel):
    """A single (underlying price, profit/loss) point of a payoff curve."""

    spot : float
    pnl  : float


class PayoffOut(BaseModel):
    """The expiry payoff curve plus the headline strategy metrics."""

    spot       : float
    lot_size   : int = 1
    curve      : list[PayoffPoint] = []
    breakevens : list[float] = []
    max_profit : float | None = None # None denotes an unbounded profit
    max_loss   : float | None = None # None denotes an unbounded loss
    net_greeks : Greeks = Greeks()
    estimated  : bool = False # True when any leg premium was inferred


class Suggestion(BaseModel):
    """A single ranked, rules-based strategy suggestion with rationale."""

    name       : str
    bias       : Literal["bullish", "bearish", "neutral", "volatile"]
    legs       : list[StrategyLeg] = []
    rationale  : list[str] = []
    score      : float = 0.0
    max_profit : float | None = None
    max_loss   : float | None = None
    breakevens : list[float] = []


class SuggestionsOut(BaseModel):
    """The ranked suggestion list plus the market context that drove it."""

    symbol      : str
    expiry      : str
    context     : dict = {}
    suggestions : list[Suggestion] = []


class HistoryPoint(BaseModel):
    """A single timestamped value of a per-strike history series."""

    ts    : str
    value : float


class HistoryOut(BaseModel):
    """A per-strike, per-leg history series for one tracked field."""

    symbol : str
    expiry : str
    strike : float
    leg    : str
    field  : str
    points : list[HistoryPoint] = []


class SocketMessage(BaseModel):
    """The envelope for every server -> client WebSocket message."""

    type   : Literal["snapshot", "tick", "status"]
    chain  : ChainOut | None = None
    state  : str | None = None
    detail : str | None = None


class SymbolInfo(BaseModel):
    """One selectable download symbol and its strike-price multiple."""

    symbol   : str
    multiple : int


class SymbolsOut(BaseModel):
    """The catalogue of selectable symbols served to the controls panel."""

    symbols : list[SymbolInfo] = []
    default : list[str] = []


class FetchRequest(BaseModel):
    """Request body for the ``Fetch Data`` control: the symbols to download."""

    symbols : list[str] = []


class WorkerStatus(BaseModel):
    """Live status of a single ``(symbol, expiry)`` download worker."""

    symbol         : str
    expiry         : str
    state          : Literal["starting", "ok", "error"] = "starting"
    snapshots      : int = 0 # distinct nse timestamps processed by the worker
    last_timestamp : str | None = None
    detail         : str | None = None


class FetchStatus(BaseModel):
    """The aggregate status of the in-process asynchronous downloader."""

    running    : bool = False
    symbols    : list[str] = []
    started_at : str | None = None
    workers    : list[WorkerStatus] = []
