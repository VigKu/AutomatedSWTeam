"""Module: backend/fastapi_stub/core.py
Purpose: Provide minimal classes/functions with FastAPI-like names.
Owner: backend
Depends on: Python standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


class status:
    """Namespace of HTTP status codes (subset)."""

    HTTP_401_UNAUTHORIZED = 401


@dataclass
class Request:
    """Placeholder Request type."""

    path: str = ""


class Header:
    """Placeholder for FastAPI Header dependency marker."""

    def __init__(self, default: Any = None):
        """Create marker.

        Args:
            default: Default value.
        """

        self.default = default


class HTTPException(Exception):
    """Exception carrying an HTTP status and a JSON-serializable detail."""

    def __init__(self, status_code: int, detail: Any):
        """Create HTTPException.

        Args:
            status_code: HTTP status.
            detail: Error detail payload.
        """

        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class FastAPI:
    """Very small router container used by our TestClient stub."""

    def __init__(self, title: str | None = None):
        """Initialize app."""

        self.title = title
        self._routes: Dict[tuple[str, str], Callable[..., Any]] = {}
        self._exception_handlers: Dict[type[BaseException], Callable[..., Any]] = {}

    def add_exception_handler(self, exc_class: type[BaseException], handler: Callable[..., Any]):
        """Register exception handler."""

        self._exception_handlers[exc_class] = handler

    def include_router(self, router: Any):
        """Include a router by copying its routes into the app."""

        for (method, path), fn in router._routes.items():
            self._routes[(method, path)] = fn

    def _register(self, method: str, path: str, fn: Callable[..., Any]):
        """Register a route."""

        self._routes[(method.upper(), path)] = fn

    def route(self, method: str, path: str):
        """Decorator for registering routes (subset)."""

        def decorator(fn: Callable[..., Any]):
            self._register(method, path, fn)
            return fn

        return decorator
