from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_reauthenticated_user
from app.core.config import settings
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.exchange_account import (
    ApiKeySecretMetadata,
    ApiKeySecretUpsert,
    ExchangeAccountCreate,
    ExchangeAccountResponse,
    ExchangeAccountUpdate,
    Phase4ReadinessReportResponse,
    Phase4SmallFundOrderWindowApprovalRequest,
    Phase4SmallFundOrderWindowApprovalResponse,
    Phase4SmallFundReviewRequest,
    Phase4SmallFundReviewResponse,
    RealReadOnlyCheckResponse,
    TestnetOrderWindowApprovalRequest,
    TestnetOrderWindowApprovalResponse,
    TestnetReadOnlyCheckResponse,
)
from app.services.exchange_accounts import (
    create_account,
    delete_account,
    delete_api_key_secret,
    get_api_key_secret_metadata,
    get_owned_account,
    list_accounts,
    update_account,
    upsert_api_key_secret,
)
from app.services.phase4_readiness import build_phase4_readiness_report
from app.services.phase4_small_fund_order_window import (
    Phase4SmallFundOrderWindowBlockedError,
    record_phase4_small_fund_order_window_approval,
)
from app.services.phase4_small_fund_review import (
    Phase4SmallFundReviewBlockedError,
    record_phase4_small_fund_review,
)
from app.services.real_read_only_check import (
    RealReadOnlyAccountNotFoundError,
    RealReadOnlyAuthenticationError,
    RealReadOnlyCheckBlockedError,
    run_real_read_only_check,
)
from app.services.testnet_order_window_approval import (
    TestnetOrderWindowApprovalBlockedError,
    record_testnet_order_window_approval,
)
from app.services.testnet_read_only_check import (
    TestnetReadOnlyAccountNotFoundError,
    TestnetReadOnlyAuthenticationError,
    TestnetReadOnlyCheckBlockedError,
    run_testnet_read_only_check,
)

router = APIRouter()


@router.get("", response_model=list[ExchangeAccountResponse])
def read_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_accounts(db, user_id=current_user.id)


@router.post("", response_model=ExchangeAccountResponse, status_code=status.HTTP_201_CREATED)
def add_account(
    payload: ExchangeAccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_account(db, user_id=current_user.id, data=payload.model_dump())


@router.get("/{account_id}", response_model=ExchangeAccountResponse)
def read_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    return account


@router.patch("/{account_id}", response_model=ExchangeAccountResponse)
def patch_account(
    account_id: str,
    payload: ExchangeAccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    return update_account(account, payload.model_dump(exclude_unset=True), db)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    delete_account(account, db)


@router.post("/{account_id}/api-key", response_model=ApiKeySecretMetadata)
def set_api_key(
    account_id: str,
    payload: ApiKeySecretUpsert,
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    secret = upsert_api_key_secret(
        db,
        user_id=current_user.id,
        exchange_account_id=account.id,
        api_key=payload.api_key,
        api_secret=payload.api_secret,
        passphrase=payload.passphrase,
    )
    return ApiKeySecretMetadata(
        exchange_account_id=account.id,
        configured=True,
        has_passphrase=secret.encrypted_passphrase is not None,
    )


@router.get("/{account_id}/api-key", response_model=ApiKeySecretMetadata)
def read_api_key_metadata(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    secret = get_api_key_secret_metadata(
        db,
        user_id=current_user.id,
        exchange_account_id=account.id,
    )
    return ApiKeySecretMetadata(
        exchange_account_id=account.id,
        configured=secret is not None,
        has_passphrase=secret is not None and secret.encrypted_passphrase is not None,
    )


@router.delete("/{account_id}/api-key", status_code=status.HTTP_204_NO_CONTENT)
def remove_api_key(
    account_id: str,
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    secret = get_api_key_secret_metadata(
        db,
        user_id=current_user.id,
        exchange_account_id=account.id,
    )
    if secret is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="api key not found")
    delete_api_key_secret(secret, db)


@router.post(
    "/{account_id}/testnet-read-only-check",
    response_model=TestnetReadOnlyCheckResponse,
)
def check_testnet_read_only_credentials(
    account_id: str,
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
) -> TestnetReadOnlyCheckResponse:
    try:
        result = run_testnet_read_only_check(
            db,
            user_id=current_user.id,
            exchange_account_id=account_id,
            testnet_adapters_enabled=settings.testnet_adapters_enabled,
        )
    except TestnetReadOnlyAccountNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="account not found",
        ) from exc
    except TestnetReadOnlyCheckBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reasons": list(exc.reasons)},
        ) from exc
    except TestnetReadOnlyAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="testnet read-only authentication failed",
        ) from exc
    return TestnetReadOnlyCheckResponse(
        exchange_account_id=result.exchange_account_id,
        exchange_name=result.exchange_name,
        authenticated=result.authenticated,
        balance_asset_count=result.balance_asset_count,
    )


@router.post(
    "/{account_id}/real-read-only-check",
    response_model=RealReadOnlyCheckResponse,
)
def check_real_read_only_credentials(
    account_id: str,
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
) -> RealReadOnlyCheckResponse:
    try:
        result = run_real_read_only_check(
            db,
            user_id=current_user.id,
            exchange_account_id=account_id,
        )
    except RealReadOnlyAccountNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="account not found",
        ) from exc
    except RealReadOnlyCheckBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reasons": list(exc.reasons)},
        ) from exc
    except RealReadOnlyAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "reason": "production read-only authentication failed",
                "failure_type": exc.failure_type,
                "exchange_code": exc.exchange_code,
            },
        ) from exc
    return RealReadOnlyCheckResponse(
        exchange_account_id=result.exchange_account_id,
        exchange_name=result.exchange_name,
        authenticated=result.authenticated,
        balance_asset_count=result.balance_asset_count,
    )


@router.post(
    "/{account_id}/testnet-order-window-approvals",
    response_model=TestnetOrderWindowApprovalResponse,
)
def approve_testnet_order_window(
    account_id: str,
    payload: TestnetOrderWindowApprovalRequest,
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
) -> TestnetOrderWindowApprovalResponse:
    try:
        approval = record_testnet_order_window_approval(
            db,
            user_id=current_user.id,
            user_role=current_user.role,
            exchange_account_id=account_id,
            symbol=payload.symbol,
            side=payload.side,
            max_quantity=payload.max_quantity,
            max_notional=payload.max_notional,
            duration_minutes=payload.duration_minutes,
            acknowledgement=payload.acknowledgement,
            testnet_adapters_enabled=settings.testnet_adapters_enabled,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="account not found",
        ) from exc
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


@router.get(
    "/{account_id}/phase4-readiness",
    response_model=Phase4ReadinessReportResponse,
)
def read_phase4_readiness(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Phase4ReadinessReportResponse:
    try:
        report = build_phase4_readiness_report(
            db,
            user=current_user,
            exchange_account_id=account_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="account not found",
        ) from exc
    return Phase4ReadinessReportResponse(
        exchange_account_id=report.exchange_account_id,
        exchange_name=report.exchange_name,
        account_mode=report.account_mode,
        overall_status=report.overall_status.value,
        read_only=report.read_only,
        order_submission_authorized=report.order_submission_authorized,
        checks=[
            {
                "name": check.name,
                "status": check.status.value,
                "required": check.required,
                "detail": check.detail,
            }
            for check in report.checks
        ],
        gate_reasons=list(report.gate_reasons),
    )


@router.post(
    "/{account_id}/phase4-small-fund-reviews",
    response_model=Phase4SmallFundReviewResponse,
)
def record_small_fund_review(
    account_id: str,
    payload: Phase4SmallFundReviewRequest,
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
) -> Phase4SmallFundReviewResponse:
    try:
        review = record_phase4_small_fund_review(
            db,
            user_id=current_user.id,
            user_role=current_user.role,
            exchange_account_id=account_id,
            max_notional=payload.max_notional,
            acknowledgement=payload.acknowledgement,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="account not found",
        ) from exc
    except Phase4SmallFundReviewBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reasons": list(exc.reasons)},
        ) from exc
    return Phase4SmallFundReviewResponse(
        audit_log_id=review.audit_log_id,
        exchange_account_id=review.exchange_account_id,
        exchange_name=review.exchange_name,
        max_notional=review.max_notional,
        read_only_audit_log_id=review.read_only_audit_log_id,
        order_submission_authorized=review.order_submission_authorized,
        trading_flags_changed=review.trading_flags_changed,
    )


@router.post(
    "/{account_id}/phase4-small-fund-order-window-approvals",
    response_model=Phase4SmallFundOrderWindowApprovalResponse,
)
def record_small_fund_order_window_approval(
    account_id: str,
    payload: Phase4SmallFundOrderWindowApprovalRequest,
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
) -> Phase4SmallFundOrderWindowApprovalResponse:
    try:
        approval = record_phase4_small_fund_order_window_approval(
            db,
            user_id=current_user.id,
            user_role=current_user.role,
            exchange_account_id=account_id,
            symbol=payload.symbol,
            side=payload.side,
            max_quantity=payload.max_quantity,
            limit_price=payload.limit_price,
            max_notional=payload.max_notional,
            duration_minutes=payload.duration_minutes,
            acknowledgement=payload.acknowledgement,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="account not found",
        ) from exc
    except Phase4SmallFundOrderWindowBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reasons": list(exc.reasons)},
        ) from exc
    return Phase4SmallFundOrderWindowApprovalResponse(
        audit_log_id=approval.audit_log_id,
        exchange_account_id=approval.exchange_account_id,
        exchange_name=approval.exchange_name,
        symbol=approval.symbol,
        side=approval.side,
        max_quantity=approval.max_quantity,
        limit_price=approval.limit_price,
        max_notional=approval.max_notional,
        duration_minutes=approval.duration_minutes,
        review_audit_log_id=approval.review_audit_log_id,
        read_only_audit_log_id=approval.read_only_audit_log_id,
        order_submission_authorized=approval.order_submission_authorized,
        trading_flags_changed=approval.trading_flags_changed,
    )
