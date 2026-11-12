"""Module: backend/tests/test_contracts.py
Purpose: Minimal unit tests for contract-level expectations.
Owner: backend
Depends on: backend app; dummy price file fixture

QA note:
Some QA environments don't install dependencies like `fastapi` and may not set
PYTHONPATH so `import backend...` fails. These tests therefore modify sys.path
to import the backend package by relative location.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so `import backend` works.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import backend.app as app_module
from backend.fastapi_stub.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    """Create app test client with a temporary prices file."""

    prices_file = tmp_path / "prices.txt"
    prices_file.write_text("AAPL 100.0\nAMD 50.5\n# comment\n", encoding="utf-8")
    os.environ["PRICES_FILE"] = str(prices_file)
    os.environ["ALLOWED_SYMBOLS"] = "AAPL,ADI,UCTT,MU,AMD,GOOGL,QCOM,META"

    app = app_module.create_app()
    return TestClient(app)


def test_prices_load_and_endpoint_contract(client: TestClient):
    """/api/prices should return parsed floats and proper envelope shape."""

    r = client.get("/api/prices?symbols=AAPL,AMD")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["error"] is None
    assert body["data"]["prices"]["AAPL"] == 100.0
    assert body["data"]["prices"]["AMD"] == 50.5
    assert isinstance(body["data"]["as_of"], str)


def test_signup_and_auth_required(client: TestClient):
    """Signup should return token; protected endpoints require auth."""

    r = client.get("/api/portfolio")
    assert r.status_code in (401, 500)
    if r.status_code == 401:
        body = r.json()
        assert body["ok"] is False
        assert body["error"]["code"] in ["AUTH_REQUIRED", "AUTH_INVALID"]

    r = client.post("/api/auth/signup", json={"name": "  Alice  "})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    token = body["data"]["token"]
    assert token

    r = client.get("/api/prices?symbols=AAPL")
    assert r.status_code == 200
    assert r.json()["data"]["prices"]["AAPL"] == 100.0

    r = client.get("/api/portfolio", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "cash" in r.json()["data"]


def test_validation_buy_and_sell(client: TestClient):
    """Validation: allowed symbols, positive qty, sell cannot exceed holdings."""

    token = client.post("/api/auth/signup", json={"name": "Bob"}).json()["data"]["token"]

    r = client.post(
        "/api/trade/buy",
        json={"symbol": "AAPL", "qty": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.json()["ok"] is False
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    r = client.post(
        "/api/trade/buy",
        json={"symbol": "NOTREAL", "qty": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.json()["ok"] is False
    assert r.json()["error"]["code"] == "SYMBOL_NOT_ALLOWED"

    # Valid buy
    r = client.post(
        "/api/trade/buy",
        json={"symbol": "AAPL", "qty": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.json()["ok"] is True
    assert r.json()["data"]["holdings"]["AAPL"] == 2

    # Cannot sell more than holdings
    r = client.post(
        "/api/trade/sell",
        json={"symbol": "AAPL", "qty": 3},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.json()["ok"] is False
    assert r.json()["error"]["code"] == "INSUFFICIENT_HOLDINGS"
