"""Test configuration for QA.

Module: backend/conftest.py
Purpose: Ensure third-party dependencies are importable during tests; provides fallback stubs when missing.
Owner: backend
Depends on: none
"""

from __future__ import annotations

# Import sitecustomize to trigger dependency stubs in constrained QA environments.
try:
    import backend.sitecustomize  # noqa: F401
except Exception:
    pass
