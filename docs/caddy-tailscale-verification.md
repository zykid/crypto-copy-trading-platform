# Caddy HTTPS and Tailscale Verification

This runbook verifies production edge access without changing trading state. It does not enable TESTNET or REAL order execution.

## Preconditions

- `PUBLIC_DOMAIN` points to the production server.
- Ports 80 and 443 are reachable from the public internet, or Caddy has a separately reviewed ACME challenge path.
- Tailscale is installed on the server and on the operator workstation.
- `.env.prod` contains real production secrets and is not committed to GitHub.

## Start Edge Services

Start the core production services and Caddy:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up --build -d postgres redis backend frontend caddy
```

Check container health:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

## Verify HTTPS

From an operator workstation:

```bash
curl -I https://$PUBLIC_DOMAIN/
curl -I https://$PUBLIC_DOMAIN/api/v1/health
```

Expected result:

- HTTP status is `200` or an expected authenticated response for protected routes.
- TLS certificate is issued for `PUBLIC_DOMAIN`.
- `Strict-Transport-Security` is present.
- No backend stack traces or secrets appear in the response.

Check Caddy logs if certificate issuance is delayed:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=200 caddy
```

## Verify Private Tailscale Access

Prefer private administration over Tailscale. Do not expose admin-only tools publicly.

On the server:

```bash
tailscale status
tailscale ip -4
```

From the operator workstation:

```bash
curl -I http://<server-tailscale-ip>:8000/api/v1/health
```

Expected result:

- The server is visible in `tailscale status`.
- The backend health endpoint is reachable over the tailnet when firewall policy allows it.
- Prometheus and Grafana remain private unless protected by explicit access controls.

## Failure Handling

- If HTTPS fails, keep trading disabled and inspect DNS, firewall, Caddy logs, and ACME rate limits.
- If Tailscale fails, keep public admin access closed and repair tailnet access before operations.
- Do not use destructive Docker cleanup commands as a certificate or networking fix.
