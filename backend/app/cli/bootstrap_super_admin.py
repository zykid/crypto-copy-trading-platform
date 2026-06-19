import argparse
import json
import os
import secrets
import sys

from app.db.session import SessionLocal
from app.services.super_admin_bootstrap import (
    SuperAdminAlreadyExistsError,
    SuperAdminBootstrapDisabledError,
    SuperAdminInputError,
    bootstrap_super_admin,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create one audited super administrator account."
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--generate-password",
        action="store_true",
        help="Generate a one-time password and print it to this terminal.",
    )
    args = parser.parse_args()

    if not args.generate_password:
        parser.error("--generate-password is required")

    password = secrets.token_urlsafe(24)
    enabled = os.getenv("SUPER_ADMIN_BOOTSTRAP_ENABLED", "").lower() == "true"

    with SessionLocal() as db:
        try:
            result = bootstrap_super_admin(
                db,
                email=args.email,
                username=args.username,
                password=password,
                enabled=enabled,
            )
        except (
            SuperAdminAlreadyExistsError,
            SuperAdminBootstrapDisabledError,
            SuperAdminInputError,
        ) as exc:
            db.rollback()
            print(str(exc), file=sys.stderr)
            return 1
        except Exception:
            db.rollback()
            print("super admin bootstrap failed", file=sys.stderr)
            return 1

    print(
        json.dumps(
            {
                "created": True,
                "user_id": result.user_id,
                "email": result.email,
                "username": result.username,
            },
            separators=(",", ":"),
        )
    )
    print(f"generated_password={password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
