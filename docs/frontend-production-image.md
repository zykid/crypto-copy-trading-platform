# Frontend Production Image

The frontend Docker image is built as a Next.js standalone production image. It is intended for staging and production-style Compose runs, not local hot-reload development.

## Build Behavior

- `frontend/next.config.mjs` enables `output: "standalone"`.
- `frontend/Dockerfile` uses separate dependency, builder, and runner stages.
- `NEXT_PUBLIC_API_BASE_URL` is passed as a Docker build argument so public Next.js values are available during `next build`.
- Runtime uses `node server.js` from the standalone output instead of `npm run dev`.
- The runner stage creates and uses a non-root `nextjs` user.
- Next.js telemetry is disabled in all image stages.

## Compose Wiring

Development Compose provides a safe local default:

```yaml
NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8000}
```

Production Compose requires an explicit value:

```yaml
NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL:?NEXT_PUBLIC_API_BASE_URL is required}
```

For Caddy-backed production deployments, set `NEXT_PUBLIC_API_BASE_URL` to the public HTTPS API base URL that browsers should call.

## Safety Notes

- Do not put API secrets, exchange secrets, JWT secrets, or encryption keys into `NEXT_PUBLIC_*` variables.
- Values prefixed with `NEXT_PUBLIC_` are browser-visible.
- This image change does not enable testnet or real trading.
- Keep `TESTNET_ADAPTERS_ENABLED=false` unless a manual testnet phase is being executed.
