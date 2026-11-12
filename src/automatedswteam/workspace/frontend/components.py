"""
Module: frontend/components.py
Purpose: UI component builders/helpers (forms, selectors, portfolio table) without business logic.
Owner: frontend
Depends on: Symbol list contract
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import gradio as gr


SYMBOLS: List[str] = ["AAPL", "ADI", "UCTT", "MU", "AMD", "GOOGL", "QCOM", "META"]


def build_account_form() -> Tuple[gr.Textbox, gr.Button, gr.Markdown]:
    """Build the account creation form components.

    Returns:
        Tuple (name_input, submit_button, status_markdown).
    """
    name_input = gr.Textbox(label="Name", placeholder="Your name", value="")
    submit_button = gr.Button("Create account")
    status = gr.Markdown("")
    return name_input, submit_button, status


def build_trade_forms() -> Tuple[gr.Dropdown, gr.Number, gr.Number, gr.Button, gr.Button]:
    """Build buy/sell trade form components.

    Returns:
        Tuple (symbol_dropdown, buy_qty, sell_qty, buy_button, sell_button).
    """
    symbol = gr.Dropdown(label="Symbol", choices=SYMBOLS, value=SYMBOLS[0], interactive=True)
    buy_qty = gr.Number(label="Buy quantity", precision=0, minimum=0, value=0)
    sell_qty = gr.Number(label="Sell quantity", precision=0, minimum=0, value=0)
    buy_btn = gr.Button("Buy")
    sell_btn = gr.Button("Sell")
    return symbol, buy_qty, sell_qty, buy_btn, sell_btn


def build_portfolio_view() -> Tuple[gr.Number, gr.Dataframe]:
    """Build portfolio view components.

    Returns:
        Tuple (cash_balance, holdings_table).
    """
    cash = gr.Number(label="Cash", precision=2, interactive=False)
    holdings = gr.Dataframe(
        headers=["Symbol", "Holdings"],
        datatype=["str", "number"],
        row_count=(len(SYMBOLS) + 1),
        col_count=(2),
        interactive=False,
        label="Holdings",
    )
    return cash, holdings


def build_prices_view() -> Tuple[gr.Dataframe, gr.Markdown]:
    """Build prices view components.

    Returns:
        Tuple (prices_table, as_of_markdown).
    """
    prices = gr.Dataframe(
        headers=["Symbol", "Price"],
        datatype=["str", "number"],
        interactive=False,
        label="Prices",
    )
    as_of = gr.Markdown("")
    return prices, as_of
