from collections.abc import Callable
from time import time

from app.services.external_alerts import ExternalAlertConfig, ExternalAlertTransports
from app.services.operational_alerts import (
    maybe_send_emergency_stop_alert,
    maybe_send_order_failure_alert,
    maybe_send_rate_limit_alert,
    maybe_send_reconciliation_drift_alert,
)


class OperationalAlertRuntime:
    def __init__(
        self,
        config: ExternalAlertConfig,
        *,
        dispatch_state: dict[str, int] | None = None,
        now_seconds_factory: Callable[[], int] | None = None,
        transports: ExternalAlertTransports | None = None,
    ) -> None:
        self.config = config
        self.dispatch_state = dispatch_state if dispatch_state is not None else {}
        self.now_seconds_factory = now_seconds_factory or _default_now_seconds
        self.transports = transports

    def notify_emergency_stop_enabled(self, *, scope: str) -> tuple[object, ...]:
        try:
            return maybe_send_emergency_stop_alert(
                scope=scope,
                config=self.config,
                now_seconds=self.now_seconds_factory(),
                dispatch_state=self.dispatch_state,
                transports=self.transports,
            )
        except Exception:
            return ()

    def notify_order_failure(
        self,
        *,
        status: str,
        failure_type: str,
    ) -> tuple[object, ...]:
        try:
            return maybe_send_order_failure_alert(
                status=status,
                failure_type=failure_type,
                config=self.config,
                now_seconds=self.now_seconds_factory(),
                dispatch_state=self.dispatch_state,
                transports=self.transports,
            )
        except Exception:
            return ()

    def notify_rate_limit(
        self,
        *,
        exchange_name: str,
        scope: str,
        request_category: str,
        retry_after_seconds: int,
    ) -> tuple[object, ...]:
        try:
            return maybe_send_rate_limit_alert(
                exchange_name=exchange_name,
                scope=scope,
                request_category=request_category,
                retry_after_seconds=retry_after_seconds,
                config=self.config,
                now_seconds=self.now_seconds_factory(),
                dispatch_state=self.dispatch_state,
                transports=self.transports,
            )
        except Exception:
            return ()

    def notify_reconciliation_drift(
        self,
        *,
        status: str,
        severity: str,
        difference_count: int,
    ) -> tuple[object, ...]:
        try:
            return maybe_send_reconciliation_drift_alert(
                status=status,
                severity=severity,
                difference_count=difference_count,
                config=self.config,
                now_seconds=self.now_seconds_factory(),
                dispatch_state=self.dispatch_state,
                transports=self.transports,
            )
        except Exception:
            return ()


def _default_now_seconds() -> int:
    return int(time())
