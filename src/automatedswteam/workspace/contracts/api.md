# Module: contracts/api.md
# Purpose: Shared API contracts
# Owner: lead
# Depends on: CODEMAP

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