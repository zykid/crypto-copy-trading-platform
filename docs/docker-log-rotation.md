# Docker Log Rotation

Docker Compose services use the `json-file` logging driver with conservative rotation defaults. This prevents long-running development, staging, or server-side mock environments from filling disks with unbounded container logs.

## Defaults

The shared Compose logging policy is:

```yaml
driver: json-file
options:
  max-size: "10m"
  max-file: "5"
```

This keeps up to five rotated log files per container, with each file capped at 10 MB unless overridden.

## Configuration

Set these values in `.env` before starting Compose:

```bash
DOCKER_LOG_MAX_SIZE=10m
DOCKER_LOG_MAX_FILE=5
```

Larger staging servers can raise these values, but production should keep finite limits and export critical audit, system event, and alert records to durable storage.

## Scope

The policy currently applies to:

- postgres
- redis
- backend
- frontend
- integration-test

Application audit records are still stored through the database-backed audit/event boundaries. Docker log rotation is only an operational guardrail for container stdout/stderr.

## Safe Operations

Use normal Compose lifecycle commands such as:

```bash
docker compose up --build -d postgres redis backend frontend
docker compose logs --tail=200 backend
docker compose down --remove-orphans
```

Do not use destructive cleanup commands for log management:

```bash
docker system prune
docker volume prune
docker network prune
docker compose down -v
```

Those commands can remove data volumes, networks, cache, or evidence needed for audit and reconciliation.
