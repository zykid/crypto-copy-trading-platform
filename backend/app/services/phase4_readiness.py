from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.trading import RiskSetting
from app.db.models.user import User, UserRole
from app.services.exchange_accounts import get_api_key_secret_metadata, get_owned_account


class Phase4ReadinessStatus(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class Phase4ReadinessCheck:
    name: str
    status: Phase4ReadinessStatus
    required: bool
    detail: str


@dataclass(frozen=True)
class Phase4ReadinessReport:
    exchange_account_id: str
    exchange_name: ExchangeName
    account_mode: AccountMode
    overall_status: Phase4ReadinessStatus
    read_only: bool
    order_submission_authorized: bool
    checks: tuple[Phase4ReadinessCheck, ...]
    gate_reasons: tuple[str, ...]


def build_phase4_readiness_report(
    db: Session,
    *,
    user: User,
    exchange_account_id: str,
) -> Phase4ReadinessReport:
    account = get_owned_account(
        db,
        user_id=user.id,
        account_id=exchange_account_id,
    )
    if account is None:
        raise ValueError("account not found")

    risk_settings = db.scalar(
        select(RiskSetting).where(
            RiskSetting.user_id == user.id,
            RiskSetting.exchange_account_id == account.id,
        )
    )
    secret = get_api_key_secret_metadata(
        db,
        user_id=user.id,
        exchange_account_id=account.id,
    )
    checks = (
        _check(
            "operator_is_super_admin",
            user.role == UserRole.SUPER_ADMIN,
            "Phase 4 readiness checks require a super administrator session.",
        ),
        _check(
            "operator_mfa_enabled",
            user.mfa_enabled,
            "Super administrator MFA must be enabled before any real-account gate.",
        ),
        _check(
            "account_is_real_okx",
            account.account_mode == AccountMode.REAL
            and account.exchange_name == ExchangeName.OKX,
            "The selected account must be an OKX REAL account.",
        ),
        _check(
            "exchange_account_active",
            account.is_active,
            "The selected exchange account must be active.",
        ),
        _check(
            "exchange_trading_disabled",
            not account.trading_enabled,
            "Exchange account trading_enabled must remain false.",
        ),
        _check(
            "risk_settings_exist",
            risk_settings is not None,
            "Risk settings must exist before Phase 4 can be proposed.",
        ),
        _check(
            "risk_trading_disabled",
            risk_settings is not None and not risk_settings.trading_enabled,
            "Risk settings trading_enabled must remain false.",
        ),
        _check(
            "api_key_metadata_configured",
            secret is not None,
            "Encrypted API key metadata must be configured.",
        ),
        _check(
            "api_key_passphrase_configured",
            secret is not None and secret.encrypted_passphrase is not None,
            "OKX REAL validation requires an encrypted passphrase.",
        ),
    )
    gate_reasons = tuple(
        check.name
        for check in checks
        if check.status == Phase4ReadinessStatus.BLOCKED
    )
    overall_status = (
        Phase4ReadinessStatus.BLOCKED
        if gate_reasons
        else Phase4ReadinessStatus.PASS
    )
    return Phase4ReadinessReport(
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        account_mode=account.account_mode,
        overall_status=overall_status,
        read_only=True,
        order_submission_authorized=False,
        checks=checks,
        gate_reasons=gate_reasons,
    )


def _check(name: str, passed: bool, detail: str) -> Phase4ReadinessCheck:
    return Phase4ReadinessCheck(
        name=name,
        status=Phase4ReadinessStatus.PASS
        if passed
        else Phase4ReadinessStatus.BLOCKED,
        required=True,
        detail=detail,
    )
