from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.trading import (
    ExecuteSignalRequest,
    OrderExecutionResponse,
    TestnetOrderAdmissionResponse,
    TestnetOrderSubmitRequest,
    TestnetOrderSubmitResponse,
    TestnetOrderWindowApprovalRequest,
    TestnetOrderWindowApprovalResponse,
    TestnetOrderWindowPlanResponse,
)
from app.services.external_alerts import ExternalAlertConfig
from app.services.operational_alert_runtime import OperationalAlertRuntime
from app.services.order_engine import execute_signal_for_account
from app.services.rate_limit_service import (
    RateLimitExceededError,
    RateLimitStoreUnavailableError,
    runtime_rate_limit_service,
)
from app.services.testnet_http_client import create_testnet_signed_http_client
from app.services.testnet_order_admission import build_testnet_order_admission_report
from app.services.testnet_order_api import (
    TestnetOrderApiBlockedError,
    build_testnet_order_api_context,
)
from app.services.testnet_order_execution import execute_testnet_order
from app.services.testnet_order_window import build_testnet_order_window_plan
from app.services.testnet_order_window_approval import (
    TestnetOrderWindowApprovalBlockedError,
    record_testnet_order_window_approval,
)

router = APIRouter()
_operational_alert_dispatch_state: dict[str, int] = {}


@router.post("/execute-signal/{signal_id}", response_model=OrderExecutionResponse)
def execute_signal(
    signal_id: str,
    payload: ExecuteSignalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return execute_signal_for_account(
            db,
            user_id=current_user.id,
            signal_id=signal_id,
            exchange_account_id=payload.exchange_account_id,
            alert_runtime=_operational_alert_runtime(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/testnet/admission-check", response_model=TestnetOrderAdmissionResponse)
def get_testnet_order_admission_check(
    exchange_account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        report = build_testnet_order_admission_report(
            db,
            user_id=current_user.id,
            exchange_account_id=exchange_account_id,
            testnet_adapters_enabled=settings.testnet_adapters_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return TestnetOrderAdmissionResponse(
        exchange_account_id=report.exchange_account_id,
        exchange_name=report.exchange_name,
        account_mode=report.account_mode.value,
        overall_status=report.overall_status.value,
        read_only=report.read_only,
        order_submission_authorized=report.order_submission_authorized,
        gate_reasons=list(report.gate_reasons),
        checks=[
            {
                "name": check.name,
                "status": check.status.value,
                "required": check.required,
                "detail": check.detail,
            }
            for check in report.checks
        ],
    )


@router.get("/testnet/window-plan", response_model=TestnetOrderWindowPlanResponse)
def get_testnet_order_window_plan(
    exchange_account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        plan = build_testnet_order_window_plan(
            db,
            user_id=current_user.id,
            exchange_account_id=exchange_account_id,
            testnet_adapters_enabled=settings.testnet_adapters_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return TestnetOrderWindowPlanResponse(
        exchange_account_id=plan.exchange_account_id,
        status=plan.status.value,
        state={
            "exchange_name": plan.state.exchange_name,
            "account_mode": plan.state.account_mode.value,
            "testnet_adapters_enabled": plan.state.testnet_adapters_enabled,
            "exchange_account_trading_enabled": plan.state.exchange_account_trading_enabled,
            "risk_settings_exist": plan.state.risk_settings_exist,
            "risk_trading_enabled": plan.state.risk_trading_enabled,
            "api_key_configured": plan.state.api_key_configured,
        },
        blocked_reasons=list(plan.blocked_reasons),
        required_operator_steps=list(plan.required_operator_steps),
        mutations_allowed=plan.mutations_allowed,
        order_submission_authorized=plan.order_submission_authorized,
    )


@router.post("/testnet/window-approval", response_model=TestnetOrderWindowApprovalResponse)
def approve_testnet_order_window(
    payload: TestnetOrderWindowApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        approval = record_testnet_order_window_approval(
            db,
            user_id=current_user.id,
            user_role=current_user.role,
            exchange_account_id=payload.exchange_account_id,
            symbol=payload.symbol,
            side=payload.side,
            max_quantity=payload.max_quantity,
            max_notional=payload.max_notional,
            duration_minutes=payload.duration_minutes,
            acknowledgement=payload.acknowledgement,
            testnet_adapters_enabled=settings.testnet_adapters_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TestnetOrderWindowApprovalBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reasons": list(exc.reasons)},
        ) from exc

    return TestnetOrderWindowApprovalResponse(
        audit_log_id=approval.audit_log_id,
        exchange_account_id=approval.exchange_account_id,
        exchange_name=approval.exchange_name,
        symbol=approval.symbol,
        side=approval.side,
        max_quantity=approval.max_quantity,
        max_notional=approval.max_notional,
        duration_minutes=approval.duration_minutes,
        order_submission_authorized=approval.order_submission_authorized,
        trading_flags_changed=approval.trading_flags_changed,
    )


@router.post("/testnet/submit", response_model=TestnetOrderSubmitResponse)
def submit_testnet_order(
    payload: TestnetOrderSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        context = build_testnet_order_api_context(
            db,
            user_id=current_user.id,
            payload=payload,
            testnet_adapters_enabled=settings.testnet_adapters_enabled,
        )
        http_client = create_testnet_signed_http_client(
            exchange_name=context.account.exchange_name,
        )
        result = execute_testnet_order(
            order=context.order,
            gate_result=context.gate_result,
            http_client=http_client,
            credentials=context.credentials,
            rate_limiter=runtime_rate_limit_service,
            exchange_account_id=context.account.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TestnetOrderApiBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reasons": list(exc.reasons)},
        ) from exc
    except RateLimitStoreUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="testnet order rate limit service unavailable",
        ) from exc
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="testnet order rate limit exceeded",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="testnet exchange request failed",
        ) from exc

    return TestnetOrderSubmitResponse(
        exchange_account_id=context.account.id,
        exchange_name=result.exchange_name,
        client_order_id=result.client_order_id,
        request_method=result.request_method,
        request_path=result.request_path,
        exchange_response=result.exchange_response,
    )


def _operational_alert_runtime() -> OperationalAlertRuntime:
    return OperationalAlertRuntime(
        ExternalAlertConfig(
            telegram_enabled=settings.telegram_alerts_enabled,
            telegram_bot_token=settings.telegram_bot_token,
            telegram_chat_id=settings.telegram_chat_id,
            email_enabled=settings.email_alerts_enabled,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_username=settings.smtp_username,
            smtp_password=settings.smtp_password,
            alert_email_from=settings.alert_email_from,
            alert_email_to=settings.alert_email_to,
            webhook_enabled=settings.webhook_alerts_enabled,
            webhook_url=settings.alert_webhook_url,
            webhook_secret=settings.alert_webhook_secret,
            timeout_seconds=settings.alert_timeout_seconds,
        ),
        dispatch_state=_operational_alert_dispatch_state,
    )
