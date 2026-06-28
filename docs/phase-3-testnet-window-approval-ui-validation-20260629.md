# Phase 3 TESTNET Order Window Approval UI Validation - 2026-06-29

This record validates the Ubuntu test deployment for the TESTNET order window approval audit UI.

It does not authorize TESTNET order submission or REAL trading.

## Scope

- Host: temporary Ubuntu integration server at `192.168.2.42`.
- Frontend: `http://192.168.2.42:3000`.
- Backend API prefix: `http://192.168.2.42:8000/api/v1`.
- Deployed commit: `aa77160`.
- Validation type: deployment, route protection, and non-mutating approval gate wiring.

## GitHub Checks

- `CI`: success for commit `aa77160`.
- `Docker Integration`: success for commit `aa77160`.

## Ubuntu Deployment

- Deployment command: `git pull --ff-only`.
- Runtime command: `docker compose up --build -d frontend backend`.
- Compose project: `trading-dev`.
- Backend container: running and healthy.
- Frontend container: running.
- PostgreSQL container: running and healthy.
- Redis container: running and healthy.

The deployment reused existing development data volumes. No destructive cleanup command was run.

## Verification

- Frontend root page returned HTTP `200`.
- Backend health endpoint returned HTTP `200`.
- Unauthenticated `POST /api/v1/orders/testnet/window-approval` returned `401 Unauthorized`.
- The frontend production build completed successfully during deployment.

## Safety Result

- No exchange API secret was read from the backend.
- No exchange API secret was returned to the frontend.
- No adapter enable action was performed.
- No account trading enable action was performed.
- No risk trading enable action was performed.
- No TESTNET or REAL order endpoint was called.
- No TESTNET or REAL order was submitted.

## Result

Pass.

The Ubuntu test deployment exposes the protected TESTNET order window approval audit path while keeping order submission unauthorized.
