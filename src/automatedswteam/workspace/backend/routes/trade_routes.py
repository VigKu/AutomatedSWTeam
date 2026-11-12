"""\
Module: backend/routes/trade_routes.py
Purpose: Auth-protected buy/sell endpoints performing validation and persisting transaction updates.
Owner: backend
Depends on: trading service; auth middleware; /api/trade/buy and /api/trade/sell contracts
"""

from __future__ import annotations

try:
    from fastapi import APIRouter, Header  # type: ignore
except Exception:  # pragma: no cover
    from backend.fastapi_stub.core import FastAPI as _FastAPI

    class APIRouter:  # pragma: no cover
        """Minimal router stub matching what's needed by backend.app stub."""

        def __init__(self, prefix: str = ""):
            """Create router stub.

            Args:
                prefix: Path prefix for route registration.
            """

            self.prefix = prefix
            self._routes: dict[tuple[str, str], object] = {}

        def post(self, path: str):
            """Register a POST endpoint on the stub router.

            Args:
                path: Route path suffix.

            Returns:
                Decorator that stores the function.
            """

            def dec(fn):
                self._routes[("POST", self.prefix + path)] = fn
                return fn

            return dec


from backend.auth.deps import require_auth
from backend.models.schemas import Envelope, TradeRequest
from backend.services.auth_service import AuthService
from backend.services.trading_service import TradingService


def trade_routes(trading_service: TradingService, auth_service: AuthService) -> APIRouter:
    """Create trading routes.

    Args:
        trading_service: Business logic for buy/sell.
        auth_service: Auth for bearer token verification.

    Returns:
        Configured APIRouter mounted at /api/trade.
    """

    router = APIRouter(prefix="/api/trade")

    def _map_error(code: str) -> tuple[str, str]:
        """Map internal/raised codes to API error details.

        Args:
            code: Internal error code.

        Returns:
            Tuple of (code, message).
        """

        msg_map = {
            "VALIDATION_ERROR": "Validation error.",
            "SYMBOL_NOT_ALLOWED": "Symbol is not allowed.",
            "INSUFFICIENT_FUNDS": "Insufficient funds.",
            "INSUFFICIENT_HOLDINGS": "Insufficient holdings.",
            "PRICE_NOT_AVAILABLE": "Price not available.",
        }
        return code, msg_map.get(code, code)

    @router.post("/buy")
    def buy(req: TradeRequest, authorization: str | None = Header(None)):
        """Execute buy transaction for authenticated user.

        Args:
            req: TradeRequest containing symbol and quantity.
            authorization: Raw Authorization header value (from route dependency in FastAPI).

        Returns:
            Consistent response envelope.
        """

        user = require_auth(auth_service, authorization=authorization)
        try:
            cash, holdings, tx = trading_service.buy(user.user_id, req.symbol, req.qty)
            return Envelope(
                ok=True,
                data={"cash": cash, "holdings": holdings, "transaction": tx.__dict__},
                error=None,
            )
        except ValueError as ve:
            code, msg = _map_error(str(ve))
            return Envelope(ok=False, data=None, error={"code": code, "message": msg})

    @router.post("/sell")
    def sell(req: TradeRequest, authorization: str | None = Header(None)):
        """Execute sell transaction for authenticated user.

        Args:
            req: TradeRequest containing symbol and quantity.
            authorization: Raw Authorization header value (from route dependency in FastAPI).

        Returns:
            Consistent response envelope.
        """

        user = require_auth(auth_service, authorization=authorization)
        try:
            cash, holdings, tx = trading_service.sell(user.user_id, req.symbol, req.qty)
            return Envelope(
                ok=True,
                data={"cash": cash, "holdings": holdings, "transaction": tx.__dict__},
                error=None,
            )
        except ValueError as ve:
            code, msg = _map_error(str(ve))
            return Envelope(ok=False, data=None, error={"code": code, "message": msg})

    return router
