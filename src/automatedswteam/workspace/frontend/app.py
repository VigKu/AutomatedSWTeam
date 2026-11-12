"""
Module: frontend/app.py
Purpose: Gradio UI entrypoint: defines layout, state, and wiring of UI components to backend API calls.
Owner: frontend
Depends on: backend contracts: /api/auth/signup, /api/prices, /api/portfolio, /api/trade/buy, /api/trade/sell; gradio
"""

from __future__ import annotations

from typing import Any, List, Tuple

import gradio as gr

from frontend.api_client import BackendError
from frontend.api_client import buy as api_buy
from frontend.api_client import fetch_portfolio as api_fetch_portfolio
from frontend.api_client import fetch_prices as api_fetch_prices
from frontend.api_client import sell as api_sell
from frontend.api_client import signup as api_signup
from frontend.components import SYMBOLS, build_account_form, build_prices_view, build_portfolio_view, build_trade_forms
from frontend.state import TokenState, token_state_component


def _validate_positive_int(value: Any, *, field: str) -> Tuple[bool, int, str]:
    """Validate that value is a positive integer (>0).

    Args:
        value: Input value.
        field: Field name for error message.

    Returns:
        Tuple (ok, parsed_int, error_message). If ok is True, error_message is ''.
    """
    try:
        v = int(value)
    except Exception:
        return False, 0, f"{field} must be an integer."
    if v <= 0:
        return False, 0, f"{field} must be a positive integer (> 0)."
    return True, v, ""


def _format_error(err: BackendError) -> str:
    """Convert BackendError to a user-facing markdown string."""
    return f"**Error ({err.code})**: {err.message}"


def _holdings_to_table(holdings: dict) -> List[List[Any]]:
    """Convert holdings dict to Dataframe rows."""
    rows: List[List[Any]] = []
    for sym in SYMBOLS:
        rows.append([sym, int(holdings.get(sym, 0) or 0)])
    return rows


def _prices_to_table(prices: dict) -> List[List[Any]]:
    """Convert prices dict to Dataframe rows."""
    rows: List[List[Any]] = []
    for sym in SYMBOLS:
        if sym in prices:
            rows.append([sym, float(prices[sym])])
        else:
            rows.append([sym, None])
    return rows


def handle_signup(name: str) -> Tuple[TokenState, str, float, List[List[Any]], List[List[Any]], str]:
    """Handle account signup.

    Args:
        name: Name input.

    Returns:
        (token_state, signup_status, cash, holdings_table, prices_table, prices_as_of)
    """
    name_clean = (name or "").strip()
    if not name_clean:
        empty_token = TokenState(token=None)
        return empty_token, "**Validation error**: Name is required.", 0.0, [], [], ""

    try:
        data = api_signup(name_clean)
        token = data["token"]

        portfolio = api_fetch_portfolio(token)
        cash = float(portfolio.get("cash", 0.0) or 0.0)
        holdings_tbl = _holdings_to_table(portfolio.get("holdings", {}) or {})

        prices, as_of = api_fetch_prices(SYMBOLS)
        prices_tbl = _prices_to_table(prices)

        user_name = (data.get("user") or {}).get("name", name_clean)
        signup_status = f"Account created for **{user_name}**. Cash: **{cash:.2f}**"

        return TokenState(token=token), signup_status, cash, holdings_tbl, prices_tbl, f"Prices as of: {as_of}"
    except BackendError as e:
        return TokenState(token=None), _format_error(e), 0.0, [], [], ""


def refresh_portfolio(token_state: TokenState) -> Tuple[float, List[List[Any]], str]:
    """Refresh portfolio panel.

    Args:
        token_state: Current token state.

    Returns:
        (cash, holdings_table, status_markdown)
    """
    if not token_state or not token_state.token:
        return 0.0, [], "**Auth required**: Please create an account."

    try:
        portfolio = api_fetch_portfolio(token_state.token)
        cash = float(portfolio.get("cash", 0.0) or 0.0)
        return cash, _holdings_to_table(portfolio.get("holdings", {}) or {}), ""
    except BackendError as e:
        return 0.0, [], _format_error(e)


def refresh_prices() -> Tuple[List[List[Any]], str]:
    """Refresh prices panel."""
    try:
        prices, as_of = api_fetch_prices(SYMBOLS)
        return _prices_to_table(prices), f"Prices as of: {as_of}"
    except BackendError as e:
        return _prices_to_table({}), _format_error(e)


def handle_buy(token_state: TokenState, symbol: str, qty: Any) -> Tuple[float, List[List[Any]], str]:
    """Handle buy action and return updated portfolio snapshot."""
    ok, parsed_qty, err = _validate_positive_int(qty, field="Buy quantity")
    if not ok:
        return 0.0, [], f"**Validation error**: {err}"

    if symbol not in SYMBOLS:
        return 0.0, [], "**Validation error**: Symbol not allowed."

    if not token_state or not token_state.token:
        return 0.0, [], "**Auth required**: Please create an account."

    try:
        result = api_buy(token_state.token, symbol, parsed_qty)
        cash = float(result.get("cash", 0.0) or 0.0)
        holdings_tbl = _holdings_to_table(result.get("holdings", {}) or {})
        tx = result.get("transaction", {}) or {}
        msg = f"Bought **{tx.get('qty', parsed_qty)} {symbol}** at **{tx.get('price', '?')}**."
        return cash, holdings_tbl, msg
    except BackendError as e:
        return 0.0, [], _format_error(e)


def handle_sell(token_state: TokenState, symbol: str, qty: Any) -> Tuple[float, List[List[Any]], str]:
    """Handle sell action and return updated portfolio snapshot."""
    ok, parsed_qty, err = _validate_positive_int(qty, field="Sell quantity")
    if not ok:
        return 0.0, [], f"**Validation error**: {err}"

    if symbol not in SYMBOLS:
        return 0.0, [], "**Validation error**: Symbol not allowed."

    if not token_state or not token_state.token:
        return 0.0, [], "**Auth required**: Please create an account."

    try:
        result = api_sell(token_state.token, symbol, parsed_qty)
        cash = float(result.get("cash", 0.0) or 0.0)
        holdings_tbl = _holdings_to_table(result.get("holdings", {}) or {})
        tx = result.get("transaction", {}) or {}
        msg = f"Sold **{tx.get('qty', parsed_qty)} {symbol}** at **{tx.get('price', '?')}**."
        return cash, holdings_tbl, msg
    except BackendError as e:
        return 0.0, [], _format_error(e)


def main() -> None:
    """Start the Gradio app."""
    with gr.Blocks(title="AutomatedSWTeam Paper Trading", analytics_enabled=False) as demo:
        gr.Markdown("# AutomatedSWTeam Paper Trading (Dummy Prices)")

        token_state = token_state_component()

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 1) Create account")
                name_input, signup_btn, signup_status = build_account_form()

            with gr.Column(scale=2):
                gr.Markdown("## 2) Portfolio")
                cash, holdings_table = build_portfolio_view()
                portfolio_status = gr.Markdown("")

                gr.Markdown("## 3) Prices")
                prices_table, prices_as_of = build_prices_view()
                price_refresh_btn = gr.Button("Refresh prices")

        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("## 4) Trade")
                symbol_dd, buy_qty, sell_qty, buy_btn, sell_btn = build_trade_forms()
                trade_status = gr.Markdown("")
            with gr.Column(scale=1):
                refresh_portfolio_btn = gr.Button("Refresh portfolio")

        signup_btn.click(
            fn=handle_signup,
            inputs=[name_input],
            outputs=[token_state, signup_status, cash, holdings_table, prices_table, prices_as_of],
        )

        refresh_portfolio_btn.click(
            fn=refresh_portfolio,
            inputs=[token_state],
            outputs=[cash, holdings_table, portfolio_status],
        )
        price_refresh_btn.click(fn=refresh_prices, inputs=[], outputs=[prices_table, prices_as_of])

        buy_btn.click(fn=handle_buy, inputs=[token_state, symbol_dd, buy_qty], outputs=[cash, holdings_table, trade_status])
        sell_btn.click(fn=handle_sell, inputs=[token_state, symbol_dd, sell_qty], outputs=[cash, holdings_table, trade_status])

        cash.value = 0.0
        holdings_table.value = _holdings_to_table({})
        prices_table.value = _prices_to_table({})

    demo.launch()


if __name__ == "__main__":
    main()

# python -m frontend.app
