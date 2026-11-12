""" 
Module: frontend/api_client.py
Purpose: Thin HTTP client wrapper for calling backend endpoints and normalizing responses to UI-friendly structures.
Owner: frontend
Depends on: Backend response envelope schema; Bearer token auth; routes: /api/auth/signup, /api/prices, /api/portfolio, /api/trade/buy, /api/trade/sell
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


@dataclass(frozen=True)
class BackendError(Exception):
    """Raised when the backend returns a non-ok response envelope.

    Args:
        code: Backend error code string.
        message: Backend error message string.
    """

    code: str
    message: str

    def __str__(self) -> str:
        """Return a human-readable error string."""

        return f"{self.code}: {self.message}"


class ApiClient:
    """Minimal HTTP client for the AutomatedSWTeam backend.

    Handles the shared response envelope: {"ok": bool, "data": ..., "error": {code,message}}.
    """

    def __init__(self, base_url: Optional[str] = None, timeout_s: float = 10.0):
        """Create an API client.

        Args:
            base_url: Base URL like http://localhost:8000. If None, uses BACKEND_BASE_URL env var or http://localhost:8000.
            timeout_s: Request timeout seconds.
        """

        self.base_url = base_url or os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
        self.timeout_s = timeout_s

    def _headers(self, token: Optional[str] = None) -> Dict[str, str]:
        """Build request headers.

        Args:
            token: Optional Bearer token.

        Returns:
            Headers dict.
        """

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            #headers["Authorization"] = token
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: Optional[str] = None,
        params: Any = None,
        json: Any = None,
    ) -> Any:
        """Execute an HTTP request and unwrap the response envelope.

        Args:
            method: HTTP method.
            path: Route path like /api/auth/signup.
            token: Optional Bearer token.
            params: Optional query params.
            json: Optional JSON body.

        Returns:
            The envelope 'data' object.

        Raises:
            BackendError: If envelope ok=false or HTTP status indicates error.
        """

        url = self.base_url.rstrip("/") + path
        resp = requests.request(
            method,
            url,
            headers=self._headers(token),
            params=params,
            json=json,
            timeout=self.timeout_s,
        )

        try:
            payload = resp.json()
        except Exception:
            resp.raise_for_status()
            raise

        if not payload.get("ok", False):
            err = payload.get("error") or {}
            raise BackendError(code=str(err.get("code", "UNKNOWN")), message=str(err.get("message", "Backend error")))

        return payload.get("data")

    def signup(self, name: str) -> Dict[str, Any]:
        """Create an account.

        Args:
            name: Account holder name.

        Returns:
            Dict like {"token": "...", "user": {"name": "...", "cash": <number>}}.
        """

        return self._request("POST", "/api/auth/signup", json={"name": name})

    def fetch_prices(self, symbols: Optional[List[str]] = None) -> Tuple[Dict[str, float], str]:
        """Fetch current dummy prices.

        Args:
            symbols: Optional list of symbols.

        Returns:
            Tuple (prices_dict, as_of_iso).
        """

        params = None
        if symbols:
            params = {"symbols": ",".join(symbols)}

        data = self._request("GET", "/api/prices", params=params)
        prices = {k: float(v) for k, v in (data.get("prices") or {}).items()}
        return prices, str(data.get("as_of", ""))

    def fetch_portfolio(self, token: str) -> Dict[str, Any]:
        """Fetch portfolio for the authenticated user.

        Args:
            token: Bearer token.

        Returns:
            Dict like {"cash": <number>, "holdings": {SYM: int, ...}, "transactions": [...]}.
        """

        return self._request("GET", "/api/portfolio", token=token)

    def buy(self, token: str, symbol: str, qty: int) -> Dict[str, Any]:
        """Buy a quantity of a symbol.

        Args:
            token: Bearer token.
            symbol: Allowed trading symbol.
            qty: Positive integer quantity.

        Returns:
            Dict like {"cash": <number>, "holdings": {...}, "transaction": {...}}.
        """

        return self._request("POST", "/api/trade/buy", token=token, json={"symbol": symbol, "qty": qty})

    def sell(self, token: str, symbol: str, qty: int) -> Dict[str, Any]:
        """Sell a quantity of a symbol.

        Args:
            token: Bearer token.
            symbol: Allowed trading symbol.
            qty: Positive integer quantity.

        Returns:
            Dict like {"cash": <number>, "holdings": {...}, "transaction": {...}}.
        """

        return self._request("POST", "/api/trade/sell", token=token, json={"symbol": symbol, "qty": qty})


_default_client = ApiClient()


def signup(name: str) -> Dict[str, Any]:
    """Convenience wrapper around the singleton API client."""

    return _default_client.signup(name)


def fetch_prices(symbols: Optional[List[str]] = None) -> Tuple[Dict[str, float], str]:
    """Convenience wrapper around the singleton API client."""

    return _default_client.fetch_prices(symbols)


def fetch_portfolio(token: str) -> Dict[str, Any]:
    """Convenience wrapper around the singleton API client."""

    return _default_client.fetch_portfolio(token)


def buy(token: str, symbol: str, qty: int) -> Dict[str, Any]:
    """Convenience wrapper around the singleton API client."""

    return _default_client.buy(token, symbol, qty)


def sell(token: str, symbol: str, qty: int) -> Dict[str, Any]:
    """Convenience wrapper around the singleton API client."""

    return _default_client.sell(token, symbol, qty)
