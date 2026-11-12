"""
Module: frontend/state.py
Purpose: Client-side state schema for token, current holdings snapshot, and last refresh timestamps.
Owner: frontend
Depends on: Gradio state mechanisms
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import gradio as gr


@dataclass
class TokenState:
    """Simple state wrapper for an auth token."""

    token: Optional[str] = None


def token_state_component() -> gr.State:
    """Create a Gradio state component for TokenState."""
    return gr.State(value=TokenState(token=None))
