"""\
Module: backend/storage/store.py
Purpose: Minimal in-memory/file-backed storage abstraction for users, holdings, cash, and transactions.
Owner: backend
Depends on: chosen persistence strategy
"""\

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from uuid import uuid4


@dataclass
class UserRecord:
    """Represents a user account."""

    user_id: str
    name: str
    cash: float
    token: str


@dataclass
class TransactionRecord:
    """Represents a trade transaction."""

    id: str
    ts: str
    type: str
    symbol: str
    qty: int
    price: float
    total: float


class Store:
    """Thread-safe storage with optional file persistence."""

    def __init__(self, persist_path: Optional[str] = None):
        """Create store.

        Args:
            persist_path: Optional JSON file to persist state.
        """

        self._lock = threading.Lock()
        self._persist_path = persist_path
        self._users_by_id: Dict[str, UserRecord] = {}
        self._user_ids_by_token: Dict[str, str] = {}
        self._holdings_by_user: Dict[str, Dict[str, int]] = {}
        self._txs_by_user: Dict[str, List[TransactionRecord]] = {}

        if persist_path and os.path.exists(persist_path):
            self._load()

    def _load(self) -> None:
        """Load persisted state from disk."""

        with open(self._persist_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        for user_id, u in raw.get("users", {}).items():
            rec = UserRecord(
                user_id=user_id,
                name=u["name"],
                cash=u["cash"],
                token=u["token"],
            )
            self._users_by_id[user_id] = rec
            self._user_ids_by_token[rec.token] = user_id

        self._holdings_by_user = raw.get("holdings", {})
        self._txs_by_user = {}
        for user_id, tx_list in raw.get("transactions", {}).items():
            self._txs_by_user[user_id] = [TransactionRecord(**tx) for tx in tx_list]

    def _persist(self) -> None:
        """Persist state to disk if configured."""

        if not self._persist_path:
            return

        os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
        raw = {
            "users": {
                uid: {
                    "name": u.name,
                    "cash": u.cash,
                    "token": u.token,
                }
                for uid, u in self._users_by_id.items()
            },
            "holdings": self._holdings_by_user,
            "transactions": {
                uid: [tx.__dict__ for tx in txs] for uid, txs in self._txs_by_user.items()
            },
        }
        tmp = self._persist_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(raw, f)
        os.replace(tmp, self._persist_path)

    def upsert_user(self, user: UserRecord) -> None:
        """Insert a new user."""

        with self._lock:
            self._users_by_id[user.user_id] = user
            self._user_ids_by_token[user.token] = user.user_id
            self._holdings_by_user.setdefault(user.user_id, {})
            self._txs_by_user.setdefault(user.user_id, [])
            self._persist()

    def get_user_by_token(self, token: str) -> Optional[UserRecord]:
        """Lookup a user by bearer token."""

        with self._lock:
            uid = self._user_ids_by_token.get(token)
            if not uid:
                return None
            return self._users_by_id.get(uid)

    def get_user_portfolio(self, user_id: str) -> Tuple[float, Dict[str, int], List[TransactionRecord]]:
        """Get cash, holdings, and tx history for a user."""

        with self._lock:
            user = self._users_by_id[user_id]
            holdings = dict(self._holdings_by_user.get(user_id, {}))
            txs = list(self._txs_by_user.get(user_id, []))
            return user.cash, holdings, txs

    def apply_trade(
        self,
        user_id: str,
        symbol: str,
        delta_qty: int,
        new_cash: float,
        tx: TransactionRecord,
    ) -> None:
        """Apply a buy/sell to update holdings, cash, and transaction history."""

        with self._lock:
            holdings = self._holdings_by_user.setdefault(user_id, {})
            holdings[symbol] = int(holdings.get(symbol, 0)) + delta_qty
            if holdings[symbol] == 0:
                holdings.pop(symbol, None)

            self._users_by_id[user_id].cash = new_cash
            self._txs_by_user.setdefault(user_id, []).append(tx)
            self._persist()

    def create_transaction_id(self) -> str:
        """Create a unique transaction id."""

        return uuid4().hex
