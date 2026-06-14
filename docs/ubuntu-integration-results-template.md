# Ubuntu Integration Results Template

Use this template to record phase 2 results without storing secrets or sensitive trading data.

## Deployment

- Date:
- Operator:
- Ubuntu host:
- Tailscale IP or MagicDNS:
- Git commit SHA:

## Preflight

- Command: `python3 scripts/integration/ubuntu_preflight.py --repo-root . --env-file .env`
- Result:

## Service Health

- Command: `docker compose ps`
- Result summary:
- Backend health URL:
- Dependency health URL:

## Mock Integration

- Command: `docker compose run --rm integration-test`
- Result:
- Command: `python3 scripts/integration/mock_compose_check.py`
- Result:

## Persistence

- Users count before restart:
- Exchange accounts count before restart:
- Order executions count before restart:
- Users count after restart:
- Exchange accounts count after restart:
- Order executions count after restart:
- Redis ping result:

## Backup Smoke Test

- Backup directory:
- Backup command result:
- Verification command result:

## Notes

Do not paste secrets, JWTs, API keys, raw exchange responses, database dumps, or sensitive IDs into this document.
