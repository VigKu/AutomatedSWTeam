"""\
Module: backend/routes/portfolio_routes.py
Purpose: Authenticated route to return portfolio cash/holdings and transaction history.
Owner: backend
Depends on: auth middleware; portfolio store; /api/portfolio contract
"""

from __future__ import annotations

try:
    from fastapi import APIRouter, Header  # type: ignore
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


from backend.auth.deps import require_auth
from backend.models.schemas import Envelope
from backend.services.auth_service import AuthService
from backend.storage.store import Store


def portfolio_route(store: Store, auth_service: AuthService) -> APIRouter:
    """Create router exposing GET /api/portfolio."""

    router = APIRouter(prefix="/api")

    @router.get("/portfolio")
    def portfolio(authorization: str | None = Header(None)):
        """Return authenticated user's portfolio."""

        user = require_auth(auth_service, authorization=authorization)
        cash, holdings, txs = store.get_user_portfolio(user.user_id)
        transactions = [
            {
                "id": tx.id,
                "ts": tx.ts,
                "type": tx.type,
                "symbol": tx.symbol,
                "qty": tx.qty,
                "price": tx.price,
                "total": tx.total,
            }
            for tx in txs
        ]
        return Envelope(ok=True, data={"cash": cash, "holdings": holdings, "transactions": transactions}, error=None)

    return router
