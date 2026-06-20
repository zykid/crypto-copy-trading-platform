from datetime import UTC, datetime

import pyotp
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret, encrypt_secret
from app.db.models.observability import AuditLog
from app.services.mfa import (
    MfaVerificationError,
    confirm_mfa_enrollment,
    disable_mfa,
    start_mfa_enrollment,
)
from app.services.users import (
    MfaRequiredError,
    authenticate_user,
    create_user,
)


def test_mfa_enrollment_encrypts_secret_and_returns_provisioning_uri(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="admin@example.com",
        username="admin",
        password="very-strong-password",
    )

    secret, provisioning_uri = start_mfa_enrollment(db_session, user=user)

    assert user.mfa_pending_secret_encrypted is not None
    assert secret not in user.mfa_pending_secret_encrypted
    assert decrypt_secret(user.mfa_pending_secret_encrypted) == secret
    assert provisioning_uri.startswith("otpauth://totp/")
    assert "Crypto%20Trading%20Platform" in provisioning_uri


def test_mfa_confirmation_enables_mfa_and_hashes_recovery_codes(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="admin@example.com",
        username="admin",
        password="very-strong-password",
    )
    secret, _ = start_mfa_enrollment(db_session, user=user)
    now = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
    code = pyotp.TOTP(secret).at(int(now.timestamp()))

    recovery_codes = confirm_mfa_enrollment(
        db_session,
        user=user,
        code=code,
        now=now,
    )

    assert user.mfa_enabled is True
    assert user.mfa_pending_secret_encrypted is None
    assert user.mfa_secret_encrypted is not None
    assert decrypt_secret(user.mfa_secret_encrypted) == secret
    assert user.auth_version == 1
    assert len(recovery_codes) == 8
    assert len(user.mfa_recovery_code_hashes) == 8
    for recovery_code in recovery_codes:
        assert recovery_code not in user.mfa_recovery_code_hashes

    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "user.mfa.enabled")
    )
    assert audit is not None
    assert secret not in str(audit.payload)
    assert code not in str(audit.payload)
    assert all(value not in str(audit.payload) for value in recovery_codes)


def test_mfa_confirmation_rejects_invalid_code(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="admin@example.com",
        username="admin",
        password="very-strong-password",
    )
    secret, _ = start_mfa_enrollment(db_session, user=user)
    now = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
    valid_code = pyotp.TOTP(secret).at(int(now.timestamp()))
    invalid_code = "000001" if valid_code == "000000" else "000000"

    with pytest.raises(MfaVerificationError):
        confirm_mfa_enrollment(
            db_session,
            user=user,
            code=invalid_code,
            now=now,
        )

    assert user.mfa_enabled is False
    assert user.auth_version == 0


def test_mfa_login_requires_code_and_rejects_totp_replay(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="admin@example.com",
        username="admin",
        password="very-strong-password",
    )
    secret = pyotp.random_base32()
    user.mfa_enabled = True
    user.mfa_secret_encrypted = encrypt_secret(secret)
    db_session.commit()
    now = datetime.now(UTC)
    code = pyotp.TOTP(secret).at(int(now.timestamp()))

    with pytest.raises(MfaRequiredError):
        authenticate_user(
            db_session,
            username_or_email=user.username,
            password="very-strong-password",
        )

    authenticated = authenticate_user(
        db_session,
        username_or_email=user.username,
        password="very-strong-password",
        mfa_code=code,
    )
    assert authenticated == user

    replay = authenticate_user(
        db_session,
        username_or_email=user.username,
        password="very-strong-password",
        mfa_code=code,
    )
    assert replay is None


def test_recovery_code_is_single_use(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="admin@example.com",
        username="admin",
        password="very-strong-password",
    )
    secret, _ = start_mfa_enrollment(db_session, user=user)
    now = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
    code = pyotp.TOTP(secret).at(int(now.timestamp()))
    recovery_codes = confirm_mfa_enrollment(
        db_session,
        user=user,
        code=code,
        now=now,
    )
    recovery_code = recovery_codes[0]

    authenticated = authenticate_user(
        db_session,
        username_or_email=user.username,
        password="very-strong-password",
        mfa_code=recovery_code,
    )
    assert authenticated == user
    assert len(user.mfa_recovery_code_hashes) == 7

    replay = authenticate_user(
        db_session,
        username_or_email=user.username,
        password="very-strong-password",
        mfa_code=recovery_code,
    )
    assert replay is None


def test_disable_mfa_clears_secrets_revokes_tokens_and_audits(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="admin@example.com",
        username="admin",
        password="very-strong-password",
    )
    secret, _ = start_mfa_enrollment(db_session, user=user)
    enabled_at = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
    enable_code = pyotp.TOTP(secret).at(int(enabled_at.timestamp()))
    recovery_codes = confirm_mfa_enrollment(
        db_session,
        user=user,
        code=enable_code,
        now=enabled_at,
    )

    disable_mfa(db_session, user=user, code=recovery_codes[0])

    assert user.mfa_enabled is False
    assert user.mfa_secret_encrypted is None
    assert user.mfa_pending_secret_encrypted is None
    assert user.mfa_last_used_step is None
    assert user.mfa_recovery_code_hashes == []
    assert user.auth_version == 2
    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "user.mfa.disabled")
    )
    assert audit is not None
    assert audit.severity == "CRITICAL"
    assert recovery_codes[0] not in str(audit.payload)


def test_disable_mfa_rejects_invalid_code_without_changing_state(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="admin@example.com",
        username="admin",
        password="very-strong-password",
    )
    secret, _ = start_mfa_enrollment(db_session, user=user)
    enabled_at = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
    enable_code = pyotp.TOTP(secret).at(int(enabled_at.timestamp()))
    confirm_mfa_enrollment(
        db_session,
        user=user,
        code=enable_code,
        now=enabled_at,
    )

    with pytest.raises(MfaVerificationError):
        disable_mfa(db_session, user=user, code="INVALID-RECOVERY-CODE")

    assert user.mfa_enabled is True
    assert user.mfa_secret_encrypted is not None
    assert len(user.mfa_recovery_code_hashes) == 8
    assert user.auth_version == 1
