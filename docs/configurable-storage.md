# Configurable Persistent Storage

The platform can keep Docker named volumes or place persistent service data below a host path selected through `TRADING_DATA_ROOT`.

This feature is opt-in. The base Compose files are unchanged and continue using named volumes unless the storage override file is included.

## Supported Paths

Development and Ubuntu integration storage:

- `${TRADING_DATA_ROOT}/postgres`
- `${TRADING_DATA_ROOT}/redis`

Production storage additionally supports:

- `${TRADING_DATA_ROOT}/backups`
- `${TRADING_DATA_ROOT}/caddy-data`
- `${TRADING_DATA_ROOT}/caddy-config`
- `${TRADING_DATA_ROOT}/prometheus`
- `${TRADING_DATA_ROOT}/grafana`

Use an absolute path on a stable Linux `ext4` or XFS filesystem. Do not use NTFS, exFAT, a removable mount with an unstable device name, or a network share for PostgreSQL data.

## New Empty Deployment

Mount the disk using its filesystem UUID through `/etc/fstab`, verify that the mount is active, then create the required directories:

```bash
sudo install -d -m 0750 /mnt/trading-data
sudo install -d -m 0750 \
  /mnt/trading-data/postgres \
  /mnt/trading-data/redis
```

Set the absolute path in the deployment environment file:

```env
TRADING_DATA_ROOT=/mnt/trading-data
```

Start the development or Ubuntu integration stack with the explicit override:

```bash
docker compose --env-file .env \
  -f docker-compose.yml \
  -f docker-compose.storage.yml \
  up -d
```

For production, prepare all listed production directories and use:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.storage.yml \
  up -d
```

Always include the same override file in later `ps`, `logs`, `run`, `up`, and `down` commands for that deployment.

## Existing Data Migration

Do not enable the override immediately on a deployment that already contains data. Docker will present empty bind-mounted directories and the application may initialize a new empty database.

A migration must be handled as a separate approved maintenance operation:

1. Verify a current PostgreSQL logical backup and its checksum.
2. Stop application writers and the database without deleting volumes.
3. Copy data while services are stopped, preserving ownership and permissions.
4. Start PostgreSQL and Redis with the override.
5. Verify Alembic revision, row counts, health checks, and application login.
6. Keep the original named volumes untouched until the migration is accepted.

Never run `docker compose down -v`, `docker volume prune`, or `docker system prune` during this process.

## Container Logs

The Compose files use bounded Docker `json-file` logging. Those files are stored below the Docker daemon data directory, not `TRADING_DATA_ROOT`.

Moving Docker logs requires changing Docker's system-wide `data-root` in `/etc/docker/daemon.json`. That affects every container on the host and requires a separate Docker maintenance procedure. It is intentionally not automated by this project.

Database backups should ideally be copied to another physical disk or remote backup target. Keeping primary data and its only backup on the same disk does not protect against disk failure.


## Super Administrator Read-only Control Plane

The backend exposes `GET /api/v1/admin/storage/locations` as groundwork for a
future Web control plane.

- Only the `super_admin` role can call the endpoint.
- Existing `admin` and normal users receive HTTP 403.
- Locations come only from the server-managed `STORAGE_LOCATION_ALLOWLIST`.
- The endpoint cannot add paths, switch storage, copy data, mount disks, or run Docker.
- Invalid allowlist configuration fails closed with HTTP 503.
- Absolute host paths are visible only to authenticated super administrators.

Example server configuration:

```env
TRADING_DATA_ROOT=/home/zykid/trading-storage-test
STORAGE_LOCATION_ALLOWLIST=test_storage=/home/zykid/trading-storage-test
```

Do not promote users to `super_admin` through public registration. Production
promotion requires a separate audited operator procedure and, before any write
operation is added, password re-authentication and MFA.
