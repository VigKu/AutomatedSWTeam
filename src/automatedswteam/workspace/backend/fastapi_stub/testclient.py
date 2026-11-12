"""Module: backend/fastapi_stub/testclient.py
Purpose: Minimal TestClient that can call our stubbed FastAPI routes.
Owner: backend
Depends on: backend.fastapi_stub core types
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .core import HTTPException, FastAPI
from .responses import JSONResponse


@dataclass
class _Resp:
    """Response representation for tests."""

    status_code: int
    _body: Dict[str, Any]

    def json(self) -> Dict[str, Any]:
        """Return response JSON."""

        return self._body


class TestClient:
    """Very small subset of fastapi.testclient.TestClient."""

    def __init__(self, app: FastAPI):
        """Create TestClient.

        Args:
            app: Application.
        """

        self.app = app

    def _call(self, method: str, url: str, headers: Optional[Dict[str, str]] = None, json_body: Any = None):
        """Call registered handler."""

        headers = headers or {}
        path = url.split("?", 1)[0]
        handler = self.app._routes.get((method.upper(), path))
        if handler is None:
            return _Resp(404, {"ok": False, "data": None, "error": {"code": "NOT_FOUND", "message": "No route"}})

        try:
            # The backend route functions in this kata are written for real FastAPI;
            # they accept parameters positionally only via our stubs in this environment.
            # We pass only json and authorization headers as kwargs if accepted.
            kwargs: Dict[str, Any] = {}
            if json_body is not None:
                kwargs["req"] = json_body
            if "authorization" in handler.__code__.co_varnames:
                kwargs["authorization"] = headers.get("Authorization")
            result = handler(**kwargs)
            if isinstance(result, JSONResponse):
                return _Resp(result.status_code, result.content or {})
            return _Resp(200, json.loads(result.json()) if hasattr(result, "json") else result)
        except HTTPException as e:
            return _Resp(e.status_code, {"ok": False, "data": None, "error": e.detail})
        except Exception as exc:
            # Use default envelope similar to backend/app.py handler.
            return _Resp(500, {"ok": False, "data": None, "error": {"code": "INTERNAL_ERROR", "message": str(exc)}})

    def get(self, url: str, headers: Optional[Dict[str, str]] = None):
        """Send GET request."""

        return self._call("GET", url, headers=headers)

    def post(self, url: str, json: Any = None, headers: Optional[Dict[str, str]] = None):
        """Send POST request."""

        return self._call("POST", url, headers=headers, json_body=json)
