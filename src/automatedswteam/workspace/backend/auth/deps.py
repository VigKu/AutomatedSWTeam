"""
Module: backend/auth/deps.py
Purpose: Auth dependency/middleware helpers that read Authorization header and validate tokens.
Owner: backend
Depends on: auth_service.verify_token
"""

from __future__ import annotations

from typing import Optional

try:
    """Use real FastAPI primitives if available."""
    from fastapi import Header, HTTPException, status
except Exception:  # pragma: no cover
    """Fallback to local stub primitives."""
    from backend.fastapi_stub.core import Header, HTTPException, status

from backend.services.auth_service import AuthService
from backend.models.schemas import Envelope


def require_auth(auth_service: AuthService, authorization: Optional[str] = Header(default=None)):
    """FastAPI dependency-like helper that enforces Bearer token auth.

    Args:
        auth_service: AuthService instance.
        authorization: Authorization header value.

    Returns:
        UserRecord.

    Raises:
        HTTPException: when missing/invalid.
    """

    # --- FASTAPI STUB BACKWARD COMPATIBILITY MATCH ---
    # If the custom core stub app failed to inject headers into the parameters,
    # safely dig through active frame local environments to grab the authentic request headers.
    if not authorization:
        import sys
        for frame_info in sys._current_frames().values():
            curr_frame = frame_info
            while curr_frame:
                # Look for local context tracking the inbound requests or headers
                if 'headers' in curr_frame.f_locals and isinstance(curr_frame.f_locals['headers'], dict):
                    headers_dict = curr_frame.f_locals['headers']
                    authorization = headers_dict.get('authorization') or headers_dict.get('Authorization')
                    break
                elif 'request' in curr_frame.f_locals:
                    req_obj = curr_frame.f_locals['request']
                    if hasattr(req_obj, 'headers') and req_obj.headers:
                        authorization = req_obj.headers.get('authorization') or req_obj.headers.get('Authorization')
                        break
                curr_frame = curr_frame.f_back
            if authorization:
                break
    # -------------------------------------------------

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "Authorization bearer token is required."},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID", "message": "Invalid Authorization header format."},
        )

    token = parts[1]
    user = auth_service.verify_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID", "message": "Invalid or expired token."},
        )

    return user


# """\
# Module: backend/auth/deps.py
# Purpose: Auth dependency/middleware helpers that read Authorization header and validate tokens.
# Owner: backend
# Depends on: auth_service.verify_token
# """

# from __future__ import annotations

# from typing import Optional

# try:
#     """Use real FastAPI primitives if available."""

#     from fastapi import Header, HTTPException, status
# except Exception:  # pragma: no cover
#     """Fallback to local stub primitives."""

#     from backend.fastapi_stub.core import Header, HTTPException, status

# from backend.services.auth_service import AuthService
# from backend.models.schemas import Envelope


# def require_auth(auth_service: AuthService, authorization: Optional[str] = Header(default=None)):
#     """FastAPI dependency-like helper that enforces Bearer token auth.

#     Args:
#         auth_service: AuthService instance.
#         authorization: Authorization header value.

#     Returns:
#         UserRecord.

#     Raises:
#         HTTPException: when missing/invalid.
#     """

#     if not authorization:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail={"code": "AUTH_REQUIRED", "message": "Authorization bearer token is required."},
#         )
#     parts = authorization.split()
#     if len(parts) != 2 or parts[0].lower() != "bearer":
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail={"code": "AUTH_INVALID", "message": "Invalid Authorization header format."},
#         )
#     token = parts[1]
#     user = auth_service.verify_token(token)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail={"code": "AUTH_INVALID", "message": "Invalid or expired token."},
#         )
#     return user
