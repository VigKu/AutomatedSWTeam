"""\
Module: backend/services/auth_service.py
Purpose: Token generation/validation and user lookup (prototype scope).
Owner: backend
Depends on: User store
"""\

from __future__ import annotations

import secrets
from typing import Optional

from backend.config import settings
from backend.storage.store import Store, UserRecord


class AuthService:
    """Authentication service for token issuance and verification."""

    def __init__(self, store: Store):
        """Create auth service.

        Args:
            store: Storage backend for users.
        """

        self._store = store

    def create_user(self, name: str) -> UserRecord:
        """Create a user record and persist it.

        Args:
            name: Display/account name.

        Returns:
            The created UserRecord including generated token.
        """

        user_id = secrets.token_hex(16)
        token = secrets.token_urlsafe(32)
        user = UserRecord(
            user_id=user_id,
            name=name,
            cash=float(settings.initial_cash),
            token=token,
        )
        self._store.upsert_user(user)
        return user

    def issue_token(self, user: UserRecord) -> str:
        """Return the token for a user.

        Args:
            user: UserRecord.

        Returns:
            Opaque bearer token.
        """

        return user.token

    def verify_token(self, token: str) -> Optional[UserRecord]:
        """Verify a bearer token.

        Args:
            token: Bearer token.

        Returns:
            UserRecord if valid; otherwise None.
        """

        return self._store.get_user_by_token(token)
