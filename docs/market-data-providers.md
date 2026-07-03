# Market Data Providers

The platform can consume third-party market data separately from exchange
execution adapters. Market data providers are read-only inputs for analysis,
manual decision support, and future signal generation. They must not place,
modify, or cancel exchange orders.

## GEXBot

GEXBot is integrated as an optional read-only market data provider.

- Official API docs: https://www.gexbot.com/apidocs
- OpenAPI reference: https://github.com/nfa-llc/gexbot-openapi
- Default base URL: `https://api.gex.bot/v2`
- Authentication: server-side `Authorization` header only

Supported V1 routes:

- `GET /api/v1/market-data/providers`
- `GET /api/v1/market-data/gexbot/tickers`
- `GET /api/v1/market-data/gexbot/classic/{ticker}/{category}`
- `GET /api/v1/market-data/gexbot/state/{ticker}/{category}`
- `GET /api/v1/market-data/gexbot/orderflow/{ticker}`

## Configuration

Set these variables in the backend environment:

```env
GEXBOT_API_BASE_URL=https://api.gex.bot/v2
GEXBOT_API_KEY=
GEXBOT_TIMEOUT_SECONDS=5
```

`GEXBOT_API_KEY` accepts any of these formats:

- raw key secret
- `gexbot_custom_<secret>`
- `Bearer gexbot_custom_<secret>`

The backend normalizes the value into the `Authorization` header. The key is
never returned to the frontend.

## Safety Rules

- Provider keys stay server-side.
- Provider keys must not be committed, logged, or shown in the browser.
- Platform routes require authenticated platform users.
- User-supplied ticker, package, and category path values are validated before
  calling the provider.
- Provider failures are mapped to platform-safe API errors.
- GEXBot data is not part of the exchange adapter interface and cannot submit
  orders.
