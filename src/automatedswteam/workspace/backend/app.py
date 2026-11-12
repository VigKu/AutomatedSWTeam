"""\
Module: backend/app.py
Purpose: Server bootstrap (FastAPI-like) that registers API routes and configures dependencies.
Owner: backend
Depends on: routes modules: auth_routes, price_routes, portfolio_routes, trade_routes; auth dependency; services and storage.
"""

from __future__ import annotations

try:
    """Try to use real fastapi if installed."""

    from fastapi import FastAPI, Request  # type: ignore
    from fastapi.responses import JSONResponse  # type: ignore
except Exception:  # pragma: no cover
    """Fallback to local stub."""

    from backend.fastapi_stub.core import FastAPI, Request
    from backend.fastapi_stub.responses import JSONResponse

from backend.config import settings
from backend.routes.auth_routes import signup_route
from backend.routes.price_routes import prices_route
from backend.routes.portfolio_routes import portfolio_route
from backend.routes.trade_routes import trade_routes
from backend.services.auth_service import AuthService
from backend.services.dummy_price_service import DummyPriceService
from backend.services.trading_service import TradingService
from backend.storage.store import Store


def _json_envelope_exception_handler(request: Request, exc: Exception):
    """Convert unhandled exceptions into our envelope JSON format."""

    status_code = 500
    detail = None
    if hasattr(exc, "status_code"):
        status_code = getattr(exc, "status_code")
    if hasattr(exc, "detail"):
        detail = getattr(exc, "detail")

    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return JSONResponse(status_code=status_code, content={"ok": False, "data": None, "error": detail})

    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "data": None,
            "error": {"code": "INTERNAL_ERROR", "message": str(detail) if detail else "Unhandled error"},
        },
    )


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(title="AutomatedSWTeam Backend")

    # Prototype storage (in-memory by default)
    store = Store(persist_path=None)
    auth_service = AuthService(store=store)
    dummy_price_service = DummyPriceService(prices_file=settings.prices_file)
    trading_service = TradingService(store=store, price_service=dummy_price_service)

    # If using real FastAPI, exception handlers work as expected.
    try:
        app.add_exception_handler(Exception, _json_envelope_exception_handler)
    except Exception:
        pass

    # Public routes
    app.include_router(signup_route(auth_service))
    app.include_router(prices_route(dummy_price_service))

    # Protected routes
    app.include_router(portfolio_route(store=store, auth_service=auth_service))
    app.include_router(trade_routes(trading_service=trading_service, auth_service=auth_service))

    return app


# Create default app instance for production servers.
app = create_app()

# uvicorn backend.app:app --reload
