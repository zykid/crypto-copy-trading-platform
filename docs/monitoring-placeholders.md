# Monitoring Placeholders

This step adds optional Prometheus and Grafana services for production planning. They are disabled by default through a Compose profile and do not scrape application business metrics yet.

## Why Optional

Trading systems should avoid publishing metrics that accidentally expose API keys, user identifiers, account identifiers, positions, orders, balances, or strategy details. The backend `/metrics` endpoint is intentionally not enabled in this step.

## Enable Monitoring Services

Set placeholder values in `.env.prod`:

```bash
PROMETHEUS_PORT=9090
PROMETHEUS_RETENTION_TIME=15d
GRAFANA_PORT=3001
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=replace-with-long-random-grafana-password
```

Start the optional profile:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile monitoring up -d prometheus grafana
```

Check logs without deleting volumes:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=200 prometheus
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=200 grafana
```

## Current Scrape Scope

`deploy/prometheus/prometheus.yml` only scrapes Prometheus itself. Future application metrics must be reviewed before enabling any backend scrape job.

## Future Metrics Review Checklist

Before exposing backend metrics, verify that metrics do not contain:

- API keys or encrypted secret material
- user email, username, or `user_id`
- exchange account IDs
- balances, exact positions, or order quantities
- client order IDs, signal IDs, execution IDs, or exchange responses
- strategy names or copy trading relationships that identify users

Prefer aggregate operational counters and histograms, such as request latency, queue depth, reconciliation drift counts by severity, and rate-limit block counts by exchange.

## Safety Notes

- Do not commit Grafana passwords or dashboard exports containing production identifiers.
- Do not expose Prometheus or Grafana directly to the public internet without authentication and network controls.
- Do not use destructive Docker cleanup commands to reset monitoring storage.
