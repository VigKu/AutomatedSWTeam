"""\
Module: backend/routes/auth_routes.py
Purpose: Route for account creation and token issuance.
Owner: backend
Depends on: /api/auth/signup contract; auth module
"""

from __future__ import annotations

try:
    from fastapi import APIRouter, Header  # type: ignore
except Exception:  # pragma: no cover
    from backend.fastapi_stub.core import FastAPI

    class APIRouter:  # pragma: no cover
        """Minimal router stub matching what's needed by backend.app stub."""

        def __init__(self, prefix: str = ""):
            self.prefix = prefix
            self._routes: dict[tuple[str, str], object] = {}

        def post(self, path: str):
            def dec(fn):
                self._routes[("POST", self.prefix + path)] = fn
                return fn

            return dec


from backend.models.schemas import Envelope, SignupRequest
from backend.services.auth_service import AuthService


def signup_route(auth_service: AuthService) -> APIRouter:
    """Create auth router with signup endpoint."""

    router = APIRouter(prefix="/api/auth")

    @router.post("/signup")
    def signup(req: SignupRequest):
        """Create account by name, generate token, and return initial cash."""

        name = (req.name or "").strip()
        if len(name) < 1:
            return Envelope(
                ok=False,
                data=None,
                error={"code": "VALIDATION_ERROR", "message": "name must be at least 1 character."},
            )

        user = auth_service.create_user(name=name)
        data = {"token": auth_service.issue_token(user), "user": {"name": user.name, "cash": user.cash}}
        return Envelope(ok=True, data=data, error=None)

    return router
