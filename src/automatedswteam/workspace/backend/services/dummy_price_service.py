"""\
Module: backend/services/dummy_price_service.py
Purpose: Reads and serves symbol->price data from a text file; exposes an interface ready to swap with a live API implementation later.
Owner: backend
Depends on: prices text file path; price parsing
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional

from backend.config import settings


class PriceService:
    """Interface for price services."""

    def get_prices(self, symbols: Optional[Iterable[str]] = None) -> Dict[str, float]:
        """Get prices for symbols.

        Args:
            symbols: Optional iterable of symbols. If None, return all available prices.

        Returns:
            Mapping of symbol -> price.
        """

        raise NotImplementedError

    def get_price(self, symbol: str) -> float:
        """Get price for a single symbol.

        Args:
            symbol: Stock symbol.

        Returns:
            Price as float.
        """

        raise NotImplementedError


class DummyPriceService(PriceService):
    """Dummy price service backed by a SYMBOL PRICE text file."""

    def __init__(self, prices_file: str):
        """Create dummy price service.

        Args:
            prices_file: Path to text file.
        """

        self._prices_file = prices_file
        self._cache: Dict[str, float] = {}
        self._as_of: Optional[str] = None
        self._load()

    def _load(self) -> None:
        """Load prices from file into cache.

        Price file format:
            one symbol per line: SYMBOL PRICE
        """

        # QA/tests set PRICES_FILE dynamically; if not present, we should still have
        # predictable behavior.
        prices: Dict[str, float] = {}
        if not os.path.exists(self._prices_file):
            # Default: if we can't find a file, populate a deterministic subset
            # from allowed symbols.
            for s in settings.allowed_symbols:
                prices[s] = 0.0
            self._cache = prices
            self._as_of = datetime.now(timezone.utc).isoformat()
            return

        with open(self._prices_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                sym = parts[0].strip().upper()
                try:
                    price = float(parts[1])
                except ValueError:
                    continue
                prices[sym] = price

        self._cache = prices
        self._as_of = datetime.now(timezone.utc).isoformat()

    def get_prices(self, symbols: Optional[Iterable[str]] = None) -> Dict[str, float]:
        """Get prices for provided symbols (or all in file if None)."""

        # For prototype: reload on each request.
        self._load()

        if symbols is None:
            return dict(self._cache)

        out: Dict[str, float] = {}
        for s in symbols:
            s_norm = str(s).strip().upper()
            if s_norm in self._cache:
                out[s_norm] = self._cache[s_norm]
        return out

    def get_price(self, symbol: str) -> float:
        """Get a single symbol price."""

        symbol_norm = symbol.strip().upper()
        self._load()
        if symbol_norm not in self._cache:
            raise KeyError(symbol_norm)
        return self._cache[symbol_norm]

    @property
    def as_of(self) -> str:
        """Return ISO8601 timestamp when prices were last loaded."""

        return self._as_of or datetime.now(timezone.utc).isoformat()
