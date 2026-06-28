# Phase 3 TESTNET Order Window Plan UI Validation - 2026-06-28

This record validates the Ubuntu test deployment for the read-only TESTNET order window planning UI.

It does not authorize TESTNET order submission or REAL trading.

## Scope

- Host: temporary Ubuntu integration server at `192.168.2.42`.
- Frontend: `http://192.168.2.42:3000`.
- Backend API prefix: `http://192.168.2.42:8000/api/v1`.
- Deployed commit: `c864878`.
- Validation type: read-only deployment and route wiring check.

## GitHub Checks

- `CI`: success for commit `c864878`.
- `Docker Integration`: success for commit `c864878`.

## Ubuntu Deployment

- Deployment command: `git pull --ff-only`.
- Runtime command: `docker compose up --build -d frontend backend`.
- Compose project: `trading-dev`.
- Backend container: running and healthy.
- Frontend container: running.
- PostgreSQL container: running and healthy.
- Redis container: running and healthy.

The deployment reused existing development data volumes. No destructive cleanup command was run.

## Read-Only Verification

- Frontend root page returned HTTP `200`.
- Unauthenticated `GET /api/v1/orders/testnet/window-plan` returned `401 Unauthorized`.
- The `401` result confirms that the window-plan route exists and remains protected when no session token is provided.
- Docker build ran the frontend production build successfully during deployment.

## Safety Result

- No exchange API secret was read from the backend.
- No exchange API secret was returned to the frontend.
- No adapter enable action was performed.
- No account trading enable action was performed.
- No risk trading enable action was performed.
- No audit approval row was written.
- No TESTNET or REAL order endpoint was called.

## Result

Pass.

The Ubuntu test deployment exposes the read-only TESTNET order window plan UI and keeps the order path closed outside a separately approved order window.
