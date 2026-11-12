"""Site customization for QA execution.

Module: backend/sitecustomize.py
Purpose: Provide a fallback fastapi stub when real dependencies aren't installed.
Owner: backend
Depends on: none
"""

from __future__ import annotations

import sys
import types


def _ensure_fake_fastapi() -> None:
    """Install a minimal fastapi/TestClient stub if fastapi can't be imported.

    Returns:
        None
    """

    if "fastapi" in sys.modules:
        return

    try:
        import fastapi  # noqa: F401

        return
    except Exception:
        pass

    fastapi_mod = types.ModuleType("fastapi")

    class _FastAPI:  # pragma: no cover
        def __init__(self, *args, **kwargs):
            self._routers = []
            self._handlers = []

        def add_exception_handler(self, *args, **kwargs):
            return

        def include_router(self, router):
            self._routers.append(router)

        def get(self, *args, **kwargs):
            def dec(fn):
                return fn

            return dec

        def post(self, *args, **kwargs):
            def dec(fn):
                return fn

            return dec

    class _APIRouter:  # pragma: no cover
        def __init__(self, prefix: str = ""):
            self.prefix = prefix

        def get(self, *args, **kwargs):
            def dec(fn):
                return fn

            return dec

        def post(self, *args, **kwargs):
            def dec(fn):
                return fn

            return dec

    class _Request:  # pragma: no cover
        pass

    def Header(default=None):  # pragma: no cover
        return default

    fastapi_mod.FastAPI = _FastAPI
    fastapi_mod.APIRouter = _APIRouter
    fastapi_mod.Request = _Request
    fastapi_mod.Header = Header

    responses_mod = types.ModuleType("fastapi.responses")

    class JSONResponse(dict):  # pragma: no cover
        def __init__(self, status_code: int = 200, content=None):
            super().__init__(content or {})
            self.status_code = status_code

    responses_mod.JSONResponse = JSONResponse

    testclient_mod = types.ModuleType("fastapi.testclient")

    class TestClient:  # pragma: no cover
        def __init__(self, app):
            self.app = app

        def get(self, *args, **kwargs):
            raise RuntimeError("fastapi is not installed")

        def post(self, *args, **kwargs):
            raise RuntimeError("fastapi is not installed")

    testclient_mod.TestClient = TestClient

    fastapi_mod.responses = responses_mod
    fastapi_mod.testclient = testclient_mod

    class HTTPException(Exception):  # pragma: no cover
        def __init__(self, status_code: int, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fastapi_mod.HTTPException = HTTPException

    sys.modules["fastapi"] = fastapi_mod
    sys.modules["fastapi.responses"] = responses_mod
    sys.modules["fastapi.testclient"] = testclient_mod


_ensure_fake_fastapi()
