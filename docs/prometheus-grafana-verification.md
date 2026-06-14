# Prometheus and Grafana Verification

Monitoring is optional and disabled by default through the Compose `monitoring` profile. This runbook verifies that the placeholders work without exposing sensitive trading data.

## Start Monitoring

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile monitoring up -d prometheus grafana dependency-health-monitor
```

The dependency health monitor remains inert unless `DEPENDENCY_HEALTH_MONITOR_ENABLED=true` is set.

## Verify Prometheus Scrape

Open Prometheus only through a private network path such as Tailscale or a protected tunnel.

Check targets:

```bash
curl -s http://<server-tailscale-ip>:9090/api/v1/targets
```

Expected targets:

- `prometheus` is up.
- `backend` scraping `backend:8000/metrics` is up.

Query safe backend flags:

```bash
curl -s 'http://<server-tailscale-ip>:9090/api/v1/query?query=trading_real_trading_enabled'
curl -s 'http://<server-tailscale-ip>:9090/api/v1/query?query=trading_testnet_adapters_enabled'
```

Expected values before later trading phases:

- `trading_real_trading_enabled` is `0`.
- `trading_testnet_adapters_enabled` is `0` unless a reviewed TESTNET phase is active.

## Starter Grafana Dashboard

Create a private dashboard with these panels:

- Backend health: `up{job="backend"}`
- Prometheus health: `up{job="prometheus"}`
- REAL trading flag: `trading_real_trading_enabled`
- TESTNET adapter flag: `trading_testnet_adapters_enabled`

Do not add labels or panels that expose user IDs, exchange account IDs, balances, positions, order IDs, quantities, prices, API keys, exchange responses, or strategy relationships.

## Review Rules for Future Metrics

Allowed metrics are aggregate operational measurements, such as:

- HTTP request count and latency by route template.
- Dependency health status by dependency name.
- Reconciliation drift count by severity.
- Rate-limit block count by exchange.
- Queue depth and worker heartbeat.

Forbidden metrics include:

- API key material or encrypted secret blobs.
- User email, username, or user ID.
- Exchange account IDs.
- Exact balances, positions, quantities, or prices.
- Signal IDs, execution IDs, client order IDs, or exchange responses.

## Failure Handling

- If Prometheus cannot scrape backend, check Compose network health and backend `/metrics` availability.
- If Grafana is unreachable, check the monitoring profile and private firewall rules.
- Do not expose monitoring ports publicly until authentication and network controls are reviewed.
