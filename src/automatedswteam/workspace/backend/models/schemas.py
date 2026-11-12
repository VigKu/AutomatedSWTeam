"""\
Module: backend/models/schemas.py
Purpose: Request/response schema definitions (types) shared by routes to ensure contract consistency.
Owner: backend
Depends on: symbol list constant
"""\

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


EnvelopeError = Dict[str, str]


class ErrorResponse(BaseModel):
    """Standard error envelope payload."""

    ok: bool = Field(default=False)
    data: None = None
    error: EnvelopeError


class Envelope(BaseModel):
    """Standard response envelope payload."""

    ok: bool
    data: Optional[Any] = None
    error: Optional[EnvelopeError] = None


class SignupRequest(BaseModel):
    """Signup request: create an account by name."""

    name: str


class SignupData(BaseModel):
    """Signup response data."""

    token: str
    user: Dict[str, Any]


class PricesResponseData(BaseModel):
    """Prices response data."""

    prices: Dict[str, float]
    as_of: str


class TransactionItem(BaseModel):
    """Single trade transaction item for portfolio."""

    id: str
    ts: str
    type: Literal["BUY", "SELL"]
    symbol: str
    qty: int
    price: float
    total: float


class PortfolioResponseData(BaseModel):
    """Portfolio response data."""

    cash: float
    holdings: Dict[str, int]
    transactions: List[TransactionItem]


class TradeRequest(BaseModel):
    """Trade request for buy/sell."""

    symbol: str
    qty: int


class TradeResponseData(BaseModel):
    """Trade response data."""

    cash: float
    holdings: Dict[str, int]
    transaction: TransactionItem
