# Phase 3 TESTNET Submit UI Validation - 2026-06-30

This record validates the Ubuntu test deployment for the guarded TESTNET submit UI and backend order-window authorization.

It does not authorize TESTNET order submission or REAL trading.

## Scope

- Host: temporary Ubuntu integration server at `192.168.2.42`.
- Frontend: `http://192.168.2.42:3000`.
- Backend API prefix: `http://192.168.2.42:8000/api/v1`.
- Deployed commit: `c7a6984`.
- Validation type: deployment, route protection, UI wiring, and backend authorization gate enforcement.

## GitHub Checks

- `CI`: success for commit `c7a6984`.
- `Docker Integration`: success for commit `c7a6984`.

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
- Frontend login page returned HTTP `200`.
- Backend health endpoint returned HTTP `200`.
- Unauthenticated `POST /api/v1/orders/testnet/submit` returned `401 Unauthorized`.
- The frontend production build completed successfully during deployment.
- The TESTNET submit UI is locked until an active bounded approval window exists.
- The backend requires a matching, unexpired append-only approval audit log before preparing an exchange request.

## Safety Result

- No exchange API secret was read from the backend.
- No exchange API secret was returned to the frontend.
- No adapter enable action was performed.
- No account trading enable action was performed.
- No risk trading enable action was performed.
- No TESTNET order was submitted.
- No REAL order endpoint was called.
- No REAL order was submitted.

## Result

Pass.

The Ubuntu test deployment exposes the guarded TESTNET submit UI while keeping the order path closed unless the backend finds a matching, unexpired approval audit record and all existing testnet gates pass.
