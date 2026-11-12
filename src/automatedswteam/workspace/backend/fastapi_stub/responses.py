"""Module: backend/fastapi_stub/responses.py
Purpose: Provide JSONResponse compatible interface.
Owner: backend
Depends on: Python standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class JSONResponse:
    """Very small JSONResponse carrying status_code and content."""

    status_code: int = 200
    content: Optional[Dict[str, Any]] = None
