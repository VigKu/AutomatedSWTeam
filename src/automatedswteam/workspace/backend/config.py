"""\
Module: backend/config.py
Purpose: Configuration: host/port, prices file path, initial cash, allowed symbols, limits.
Owner: backend
Depends on: environment variables
"""\

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    allowed_symbols: List[str]
    prices_file: str
    initial_cash: float
    max_qty: int


def _parse_symbols(raw: str) -> List[str]:
    """Parse comma-separated symbols from env var."""

    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def load_settings() -> Settings:
    """Load settings from environment variables with safe defaults."""

    allowed_raw = os.environ.get(
        "ALLOWED_SYMBOLS", "AAPL,ADI,UCTT,MU,AMD,GOOGL,QCOM,META"
    )
    prices_file = os.environ.get(
        "PRICES_FILE",
        os.path.join(os.path.dirname(__file__), "prices.txt"),
    )
    initial_cash = float(os.environ.get("INITIAL_CASH", "100000"))
    max_qty = int(os.environ.get("MAX_QTY", "1000000"))

    return Settings(
        allowed_symbols=_parse_symbols(allowed_raw),
        prices_file=prices_file,
        initial_cash=initial_cash,
        max_qty=max_qty,
    )


settings: Settings = load_settings()
