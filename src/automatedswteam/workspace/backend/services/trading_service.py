"""\
Module: backend/services/trading_service.py
Purpose: Validates buy/sell, calculates totals, updates cash/holdings, records transactions (prototype storage).
Owner: backend
Depends on: dummy_price_service for price; portfolio store
"""\

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Tuple

from backend.config import settings
from backend.services.dummy_price_service import PriceService
from backend.storage.store import Store, TransactionRecord


class TradingService:
    """Business logic for buy and sell operations."""

    def __init__(self, store: Store, price_service: PriceService):
        """Create trading service.

        Args:
            store: Portfolio/users storage.
            price_service: Price provider.
        """

        self._store = store
        self._price_service = price_service

    def _validate_common(self, symbol: str, qty: int) -> str | None:
        """Validate symbol and qty. Returns error code or None."""

        if qty is None:
            return "VALIDATION_ERROR"
        if not isinstance(qty, int) or qty <= 0:
            return "VALIDATION_ERROR"
        if qty > settings.max_qty:
            return "VALIDATION_ERROR"

        symbol = symbol.strip().upper()
        if symbol not in settings.allowed_symbols:
            return "SYMBOL_NOT_ALLOWED"
        return None

    def buy(self, user_id: str, symbol: str, qty: int) -> Tuple[float, Dict[str, int], TransactionRecord]:
        """Buy shares for a user.

        Args:
            user_id: Authenticated user id.
            symbol: Stock symbol.
            qty: Positive integer quantity.

        Returns:
            Tuple of (cash, holdings, transaction).

        Raises:
            ValueError with error code message keys for API mapping.
        """

        symbol = symbol.strip().upper()
        err = self._validate_common(symbol, qty)
        if err:
            raise ValueError(err)

        try:
            price = float(self._price_service.get_price(symbol))
        except KeyError:
            raise ValueError("PRICE_NOT_AVAILABLE")

        total = price * qty
        cash, holdings, _ = self._store.get_user_portfolio(user_id)
        if total > cash:
            raise ValueError("INSUFFICIENT_FUNDS")

        new_cash = cash - total
        tx = TransactionRecord(
            id=self._store.create_transaction_id(),
            ts=datetime.now(timezone.utc).isoformat(),
            type="BUY",
            symbol=symbol,
            qty=qty,
            price=price,
            total=total,
        )
        self._store.apply_trade(user_id=user_id, symbol=symbol, delta_qty=qty, new_cash=new_cash, tx=tx)
        cash2, holdings2, _ = self._store.get_user_portfolio(user_id)
        return cash2, holdings2, tx

    def sell(self, user_id: str, symbol: str, qty: int) -> Tuple[float, Dict[str, int], TransactionRecord]:
        """Sell shares for a user.

        Args:
            user_id: Authenticated user id.
            symbol: Stock symbol.
            qty: Positive integer quantity.

        Returns:
            Tuple of (cash, holdings, transaction).

        Raises:
            ValueError with error code.
        """

        symbol = symbol.strip().upper()
        err = self._validate_common(symbol, qty)
        if err:
            raise ValueError(err)

        cash, holdings, _ = self._store.get_user_portfolio(user_id)
        current_qty = int(holdings.get(symbol, 0))
        if qty > current_qty:
            raise ValueError("INSUFFICIENT_HOLDINGS")

        try:
            price = float(self._price_service.get_price(symbol))
        except KeyError:
            raise ValueError("PRICE_NOT_AVAILABLE")

        total = price * qty
        new_cash = cash + total
        tx = TransactionRecord(
            id=self._store.create_transaction_id(),
            ts=datetime.now(timezone.utc).isoformat(),
            type="SELL",
            symbol=symbol,
            qty=qty,
            price=price,
            total=total,
        )
        self._store.apply_trade(user_id=user_id, symbol=symbol, delta_qty=-qty, new_cash=new_cash, tx=tx)
        cash2, holdings2, _ = self._store.get_user_portfolio(user_id)
        return cash2, holdings2, tx
