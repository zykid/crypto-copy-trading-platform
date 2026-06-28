from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.observability import AuditLog
from app.db.models.trading import RiskSetting
from app.exchanges.testnet_config import TESTNET_ENDPOINTS
from app.services.exchange_accounts import get_api_key_secret_metadata, get_owned_account
from app.services.testnet_order_gate import check_testnet_order_gate


class TestnetOrderAdmissionStatus(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class TestnetOrderAdmissionCheck:
    name: str
    status: TestnetOrderAdmissionStatus
    required: bool
    detail: str


@dataclass(frozen=True)
class TestnetOrderAdmissionReport:
    exchange_account_id: str
    exchange_name: ExchangeName
    account_mode: AccountMode
    overall_status: TestnetOrderAdmissionStatus
    checks: tuple[TestnetOrderAdmissionCheck, ...]
    gate_reasons: tuple[str, ...]
    read_only: bool = True
    order_submission_authorized: bool = False


def build_testnet_order_admission_report(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    testnet_adapters_enabled: bool,
) -> TestnetOrderAdmissionReport:
    account = get_owned_account(
        db,
        user_id=user_id,
        account_id=exchange_account_id,
    )
    if account is None:
        raise ValueError("account not found")

    risk_settings = db.scalar(
        select(RiskSetting).where(
            RiskSetting.user_id == user_id,
            RiskSetting.exchange_account_id == account.id,
        )
    )
    secret_metadata = get_api_key_secret_metadata(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
    )
    gate_result = check_testnet_order_gate(
        exchange_name=account.exchange_name,
        account_mode=account.account_mode,
        testnet_adapters_enabled=testnet_adapters_enabled,
        exchange_account_trading_enabled=account.trading_enabled,
        risk_trading_enabled=risk_settings.trading_enabled if risk_settings else False,
        api_key_configured=secret_metadata is not None,
        manual_testnet_order_enable_confirmed=False,
    )

    checks = (
        _check(
            "exchange_supports_testnet_order_routing",
            account.exchange_name in TESTNET_ENDPOINTS,
            "exchange has a configured testnet/demo endpoint",
            "exchange is not supported for testnet order routing",
        ),
        _check(
            "account_mode_is_testnet",
            account.account_mode == AccountMode.TESTNET,
            "account mode is TESTNET",
            "account mode must be TESTNET",
        ),
        _check(
            "testnet_adapters_disabled_before_window",
            not testnet_adapters_enabled,
            "TESTNET_ADAPTERS_ENABLED is false before an approved order window",
            "TESTNET_ADAPTERS_ENABLED is already true; verify rollback before proceeding",
        ),
        _check(
            "exchange_account_trading_disabled_before_window",
            not account.trading_enabled,
            "exchange account trading is disabled before an approved order window",
            "exchange account trading is already enabled",
        ),
        _check(
            "risk_settings_exist",
            risk_settings is not None,
            "risk settings exist for the account",
            "risk settings must exist before admission",
        ),
        _check(
            "risk_trading_disabled_before_window",
            risk_settings is not None and not risk_settings.trading_enabled,
            "risk setting trading is disabled before an approved order window",
            "risk setting trading is enabled or missing",
        ),
        _check(
            "encrypted_api_key_metadata_configured",
            secret_metadata is not None,
            "encrypted API key metadata exists without exposing secret material",
            "encrypted API key metadata is missing",
        ),
        _check(
            "audit_log_table_readable",
            _audit_log_table_readable(db),
            "audit log table is readable; this probe does not write audit rows",
            "audit log table is not readable",
        ),
        _check(
            "current_order_gate_blocks_submission",
            not gate_result.approved,
            "current gate blocks submission because no manual order approval is accepted here",
            "current gate unexpectedly approves order submission",
        ),
    )
    overall_status = (
        TestnetOrderAdmissionStatus.PASS
        if all(
            check.status == TestnetOrderAdmissionStatus.PASS
            for check in checks
            if check.required
        )
        else TestnetOrderAdmissionStatus.BLOCKED
    )
    return TestnetOrderAdmissionReport(
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        account_mode=account.account_mode,
        overall_status=overall_status,
        checks=checks,
        gate_reasons=gate_result.reasons,
    )


def _check(
    name: str,
    condition: bool,
    pass_detail: str,
    fail_detail: str,
) -> TestnetOrderAdmissionCheck:
    return TestnetOrderAdmissionCheck(
        name=name,
        status=(
            TestnetOrderAdmissionStatus.PASS
            if condition
            else TestnetOrderAdmissionStatus.BLOCKED
        ),
        required=True,
        detail=pass_detail if condition else fail_detail,
    )


def _audit_log_table_readable(db: Session) -> bool:
    try:
        db.execute(select(AuditLog.id).limit(1)).first()
    except SQLAlchemyError:
        return False
    return True
