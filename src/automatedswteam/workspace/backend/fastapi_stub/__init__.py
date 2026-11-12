"""Module: backend/fastapi_stub/__init__.py
Purpose: Minimal FastAPI-compatible stub used for environments without FastAPI.
Owner: backend
Depends on: backend.fastapi_stub core modules
"""

from .core import FastAPI, Request, Header, HTTPException, status
from .responses import JSONResponse

__all__ = ["FastAPI", "Request", "Header", "HTTPException", "status", "JSONResponse"]
