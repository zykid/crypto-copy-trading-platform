import hashlib
import hmac
import secrets
from datetime import UTC, datetime

import pyotp
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import decrypt_secret, encrypt_secret
from app.db.models.observability import AuditLog
from app.db.models.user import User

_TOTP_INTERVAL_SECONDS = 30
_TOTP_VALID_WINDOW = 1
_RECOVERY_CODE_COUNT = 8


class MfaEnrollmentError(ValueError):
    pass


class MfaVerificationError(ValueError):
    pass


def get_mfa_status(user: User) -> tuple[bool, bool]:
    return user.mfa_enabled, user.mfa_pending_secret_encrypted is not None


def start_mfa_enrollment(
    db: Session,
    *,
    user: User,
    issuer_name: str = "Crypto Trading Platform",
) -> tuple[str, str]:
    if user.mfa_enabled:
        raise MfaEnrollmentError("mfa is already enabled")

    secret = pyotp.random_base32()
    user.mfa_pending_secret_encrypted = encrypt_secret(secret)
    db.add(
        AuditLog(
            user_id=user.id,
            exchange_account_id=None,
            action="user.mfa.enrollment.started",
            severity="INFO",
            payload={"user_id": user.id},
        )
    )
    db.commit()

    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email,
        issuer_name=issuer_name,
    )
    return secret, provisioning_uri


def confirm_mfa_enrollment(
    db: Session,
    *,
    user: User,
    code: str,
    now: datetime | None = None,
) -> list[str]:
    encrypted_secret = user.mfa_pending_secret_encrypted
    if user.mfa_enabled or encrypted_secret is None:
        raise MfaEnrollmentError("mfa enrollment is not pending")

    secret = decrypt_secret(encrypted_secret)
    matched_step = _match_totp(
        secret=secret,
        code=code,
        last_used_step=None,
        now=now,
    )
    if matched_step is None:
        raise MfaVerificationError("invalid mfa code")

    recovery_codes = [_generate_recovery_code() for _ in range(_RECOVERY_CODE_COUNT)]
    user.mfa_secret_encrypted = encrypted_secret
    user.mfa_pending_secret_encrypted = None
    user.mfa_enabled = True
    user.mfa_last_used_step = matched_step
    user.mfa_recovery_code_hashes = [
        _hash_recovery_code(code_value) for code_value in recovery_codes
    ]
    user.auth_version += 1
    db.add(
        AuditLog(
            user_id=user.id,
            exchange_account_id=None,
            action="user.mfa.enabled",
            severity="WARNING",
            payload={
                "user_id": user.id,
                "recovery_code_count": len(recovery_codes),
                "new_auth_version": user.auth_version,
            },
        )
    )
    db.commit()
    return recovery_codes


def verify_mfa_challenge(
    db: Session,
    *,
    user: User,
    code: str,
    now: datetime | None = None,
) -> bool:
    if not user.mfa_enabled or user.mfa_secret_encrypted is None:
        return False

    normalized = _normalize_recovery_code(code)
    if not code.isdigit():
        candidate_hash = _hash_recovery_code(normalized)
        remaining = [
            stored_hash
            for stored_hash in user.mfa_recovery_code_hashes
            if not hmac.compare_digest(stored_hash, candidate_hash)
        ]
        if len(remaining) == len(user.mfa_recovery_code_hashes):
            return False
        user.mfa_recovery_code_hashes = remaining
        db.add(
            AuditLog(
                user_id=user.id,
                exchange_account_id=None,
                action="user.mfa.recovery_code.used",
                severity="WARNING",
                payload={
                    "user_id": user.id,
                    "remaining_recovery_codes": len(remaining),
                },
            )
        )
        return True

    secret = decrypt_secret(user.mfa_secret_encrypted)
    matched_step = _match_totp(
        secret=secret,
        code=code,
        last_used_step=user.mfa_last_used_step,
        now=now,
    )
    if matched_step is None:
        return False
    user.mfa_last_used_step = matched_step
    return True


def _match_totp(
    *,
    secret: str,
    code: str,
    last_used_step: int | None,
    now: datetime | None,
) -> int | None:
    if len(code) != 6 or not code.isdigit():
        return None

    timestamp = int((now or datetime.now(UTC)).timestamp())
    current_step = timestamp // _TOTP_INTERVAL_SECONDS
    totp = pyotp.TOTP(secret, interval=_TOTP_INTERVAL_SECONDS)
    for offset in range(-_TOTP_VALID_WINDOW, _TOTP_VALID_WINDOW + 1):
        candidate_step = current_step + offset
        if last_used_step is not None and candidate_step <= last_used_step:
            continue
        expected = totp.at(candidate_step * _TOTP_INTERVAL_SECONDS)
        if hmac.compare_digest(expected, code):
            return candidate_step
    return None


def _generate_recovery_code() -> str:
    value = secrets.token_hex(8).upper()
    return "-".join(value[index : index + 4] for index in range(0, len(value), 4))


def _normalize_recovery_code(code: str) -> str:
    return code.replace("-", "").replace(" ", "").upper()


def _hash_recovery_code(code: str) -> str:
    normalized = _normalize_recovery_code(code)
    return hmac.new(
        settings.secret_encryption_key.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
