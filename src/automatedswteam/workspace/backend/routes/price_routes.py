"""\
Module: backend/routes/price_routes.py
Purpose: Route to fetch dummy prices from file (and later replaceable service).
Owner: backend
Depends on: dummy_price_service interface; /api/prices contract
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

try:
    from fastapi import APIRouter, Query, Header  # type: ignore
except Exception:  # pragma: no cover

    class APIRouter:  # pragma: no cover
        """Minimal router stub."""

        def __init__(self, prefix: str = ""):
            self.prefix = prefix
            self._routes: dict[tuple[str, str], object] = {}

        def get(self, path: str):
            def dec(fn):
                self._routes[("GET", self.prefix + path)] = fn
                return fn

            return dec

    def Query(default=None):  # pragma: no cover
        """Placeholder for FastAPI Query."""

        return default

from backend.models.schemas import Envelope
from backend.services.dummy_price_service import PriceService


def prices_route(price_service: PriceService) -> APIRouter:
    """Create pricing router exposing GET /api/prices."""

    router = APIRouter(prefix="/api")

    @router.get("/prices")
    def prices(symbols: Optional[str] = Query(default=None)):
        """Get current dummy prices for optional comma-separated symbols."""

        sym_list: Optional[List[str]] = None
        if symbols:
            sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

        try:
            prices_map = price_service.get_prices(sym_list)
            as_of = datetime.now(timezone.utc).isoformat()
            return Envelope(ok=True, data={"prices": prices_map, "as_of": as_of}, error=None)
        except Exception as e:
            return Envelope(ok=False, data=None, error={"code": "PRICE_NOT_AVAILABLE", "message": str(e)})

    return router
