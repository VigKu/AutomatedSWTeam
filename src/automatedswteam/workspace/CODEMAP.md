# CODEMAP: stocks-gradio-prototype

A two-folder Python/Gradio prototype for stock trading with account creation and paper trading (buy/sell) across a fixed watchlist. The backend provides a dummy price API backed by a text file (designed to be replaceable by a live market API later), simple auth for session-based access, and transaction/portfolio endpoints. The frontend is a Gradio-only UI that calls backend routes, renders portfolio/holdings, and drives buy/sell flows. Application logic is intentionally not written here—only architecture, contracts, and file structure are specified.

Use this index to find the file that owns a feature before reading or editing.

## frontend
- `frontend/api_client.py` — Thin HTTP client wrapper for calling backend endpoints and normalizing responses to UI-friendly structures (fixed syntax).
  - exports: ApiClient class; BackendError; signup/fetch_prices/fetch_portfolio/buy/sell convenience functions
  - depends_on: Backend response envelope schema; Bearer token auth; routes /api/auth/signup,/api/prices,/api/portfolio,/api/trade/buy,/api/trade/sell
- `frontend/app.py` — Fix Gradio UI wiring and ensure required account/trade/portfolio/prices panels with Gradio state for auth token and error handling; refresh portfolio/prices after transactions.
  - exports: main
  - depends_on: frontend/api_client.py; frontend/components.py; frontend/state.py; backend routes /api/auth/signup, /api/prices, /api/portfolio, /api/trade/buy, /api/trade/sell; gradio
- `frontend/components.py` — Build minimal Gradio components for account creation, trade buy/sell forms, portfolio and prices panels; no business logic.
  - exports: build_account_form, build_trade_forms, build_portfolio_view, build_prices_view, SYMBOLS
  - depends_on: Symbol list contract
- `frontend/state.py` — Define Gradio state structures for auth token and last snapshots/timestamps; provide helper utilities only.
  - exports: TokenState
  - depends_on: Gradio state mechanisms

## backend
- `backend/app.py` — FastAPI bootstrap registering routes and configuring services/storage.
  - exports: app, create_app
  - depends_on: backend.auth.deps.require_auth; backend.config.settings; backend.routes.auth_routes.signup_route; backend.routes.price_routes.prices_route; backend.routes.portfolio_routes.portfolio_route; backend.routes.trade_routes.trade_routes; backend.services.auth_service.AuthService; backend.services.dummy_price_service.DummyPriceService; backend.services.trading_service.TradingService; backend.storage.store.Store
- `backend/auth/deps.py` — Auth dependency/middleware helpers that read Authorization header and validate tokens.
  - exports: require_auth().
  - depends_on: auth_service.verify_token
- `backend/config.py` — Configuration for allowed symbols, prices file, initial cash, and qty limits.
  - exports: Settings, settings, load_settings
  - depends_on: environment variables
- `backend/models/schemas.py` — Pydantic request/response envelope schemas and models shared by routes.
  - exports: Envelope, SignupRequest, PricesResponseData, PortfolioResponseData, TradeRequest, TradeResponseData, ErrorResponse
  - depends_on: allowed symbols contract
- `backend/routes/auth_routes.py` — Route for account creation and token issuance.
  - exports: signup_route.
  - depends_on: /api/auth/signup contract; auth module
- `backend/routes/portfolio_routes.py` — Authenticated route to return portfolio cash/holdings and recent transactions.
  - exports: portfolio_route.
  - depends_on: auth middleware; portfolio store; /api/portfolio contract
- `backend/routes/price_routes.py` — Route to fetch dummy prices from file (and later replaceable service).
  - exports: prices_route.
  - depends_on: dummy_price_service interface; /api/prices contract
- `backend/routes/trade_routes.py` — Auth-protected buy/sell endpoints with consistent envelope and error mapping to required error codes.
  - exports: trade_routes, buy_route, sell_route
  - depends_on: backend.auth.deps.require_auth; backend.services.trading_service.TradingService; backend.models.schemas.Envelope, TradeRequest
- `backend/services/auth_service.py` — Token generation and validation plus user creation.
  - exports: AuthService, create_user, issue_token, verify_token
  - depends_on: Store
- `backend/services/dummy_price_service.py` — Implements dummy price service backed by SYMBOL PRICE text file; supports replaceable interface via PriceService and provides get_prices/get_price.
  - exports: PriceService, DummyPriceService
  - depends_on: backend/config.py, prices text file parsing
- `backend/services/trading_service.py` — Validates buy/sell, calculates totals, updates cash/holdings, records transactions (prototype storage).
  - exports: buy(user_id,symbol,qty), sell(user_id,symbol,qty).
  - depends_on: dummy_price_service for price; portfolio store
- `backend/sitecustomize.py` — Fix QA import/runtime issues by ensuring fastapi stubs include TestClient and minimal routing/response handling so backend tests can run without FastAPI installed.
  - exports: _ensure_fake_fastapi
  - depends_on: none
- `backend/storage/store.py` — Thread-safe in-memory (optionally file-persisted) storage for users, cash, holdings, transactions.
  - exports: Store, UserRecord, TransactionRecord
  - depends_on: chosen persistence strategy
- `backend/tests/test_contracts.py` — Contract-level unit tests for envelope/validation/auth and dummy price loading.
  - exports: pytest tests
  - depends_on: backend app test client; dummy price file fixture

## contracts

Shared contracts (routes, payloads, auth):

Auth model
- Auth method: Bearer token
- Token: opaque string returned at account creation
- Client includes header: Authorization: Bearer <token>
- Protected routes: /api/portfolio, /api/trade/buy, /api/trade/sell

Symbols (allowed set)
- ["AAPL","ADI","UCTT","MU","AMD","GOOGL","QCOM","META"]

Base URL
- Assume: http://<host>:<port>
- All endpoints under: /api

Response envelope (recommended, used by all endpoints)
- Success: {"ok": true, "data": <object>, "error": null}
- Error:   {"ok": false, "data": null, "error": {"code": <string>, "message": <string>}}

1) Create account
- POST /api/auth/signup
- Request body: {"name": "<string>"}
- Validation: name required, trim whitespace, min length (e.g., >= 1)
- Response: {"ok": true, "data": {"token": "<token>", "user": {"name": "...", "cash": <number>}}}

2) Get current prices
- GET /api/prices?symbols=AAPL,ADI,... (optional)
- Response data: {"prices": {"AAPL": <number>, ...}, "as_of": "<ISO8601>"}

3) Get portfolio
- GET /api/portfolio
- Auth required
- Response data: {
  "cash": <number>,
  "holdings": {"AAPL": <int>, "ADI": <int>, ...},
  "transactions": [
    {"id":"<string>","ts":"<ISO8601>","type":"BUY|SELL","symbol":"AAPL","qty":<int>,"price":<number>,"total":<number>}
  ]
}

4) Buy
- POST /api/trade/buy
- Auth required
- Request body: {"symbol":"AAPL","qty": <int>}
- Pricing rule (prototype): use current dummy price from /api/prices at time of request
- Response data: {"cash": <number>, "holdings": {"AAPL": <int>, ...}, "transaction": { ...same fields as above... }}

5) Sell
- POST /api/trade/sell
- Auth required
- Request body: {"symbol":"AAPL","qty": <int>}
- Validation: qty <= current holdings for symbol
- Response data: same structure as buy.

Error codes (suggested)
- AUTH_REQUIRED, AUTH_INVALID
- VALIDATION_ERROR (with message)
- INSUFFICIENT_FUNDS
- INSUFFICIENT_HOLDINGS
- SYMBOL_NOT_ALLOWED
- PRICE_NOT_AVAILABLE

Dummy price contract (internal to backend)
- Price file format (example): one symbol per line: SYMBOL PRICE
  Example lines: AAPL 189.42
  - Backend should parse and expose as float.
- as_of timestamp should be current time when loaded (or when served).
