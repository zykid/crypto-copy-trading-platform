SAFE_DEPENDENCY_NAMES = frozenset({"database", "redis", "backend", "frontend", "caddy"})
SAFE_DEPENDENCY_STATES = frozenset({"ok", "degraded", "unavailable", "unknown"})
SAFE_EXCHANGE_NAMES = frozenset({"binance", "bybit", "mock", "okx"})
SAFE_ORDER_FAILURE_STATUSES = frozenset({"FAILED", "REJECTED", "TIMEOUT"})
SAFE_ORDER_FAILURE_TYPES = frozenset(
    {
        "exchange_failed",
        "exchange_rejected",
        "rate_limited",
        "risk_rejected",
        "timeout",
        "unknown",
    }
)
SAFE_RATE_LIMIT_SCOPES = frozenset({"account", "global", "ip"})
SAFE_RATE_LIMIT_REQUEST_CATEGORIES = frozenset({"market_data", "order", "private", "unknown"})
DEPENDENCY_HEALTH_ALERT_KEY = "dependency_health"
ORDER_FAILURE_ALERT_KEY_PREFIX = "order_failure"
RATE_LIMIT_ALERT_KEY_PREFIX = "rate_limit"
DEFAULT_DEPENDENCY_ALERT_THROTTLE_SECONDS = 300
DEFAULT_ORDER_FAILURE_ALERT_THROTTLE_SECONDS = 300
DEFAULT_RATE_LIMIT_ALERT_THROTTLE_SECONDS = 300


def build_dependency_health_alert(
    checks: dict[str, str],
) -> object | None:
    status = _safe_state(checks.get("status", "unknown"))
    if status == "ok":
        return None

    affected = tuple(
        name
        for name, state in sorted(checks.items())
        if name in SAFE_DEPENDENCY_NAMES and _safe_state(state) != "ok"
    )
    affected_value = ",".join(affected) if affected else "unknown"

    from app.services.external_alerts import ExternalAlertEvent

    return ExternalAlertEvent(
        severity="warning" if status == "degraded" else "critical",
        title="Service dependency health degraded",
        message="One or more platform dependencies are not healthy.",
        metadata={
            "component": "health_check",
            "status": status,
            "affected_dependencies": affected_value,
        },
    )


def build_order_failure_alert(*, status: str, failure_type: str) -> object | None:
    safe_status = _safe_order_failure_status(status)
    if safe_status is None:
        return None

    from app.services.external_alerts import ExternalAlertEvent

    safe_failure_type = _safe_order_failure_type(failure_type)
    return ExternalAlertEvent(
        severity="critical" if safe_status in {"FAILED", "TIMEOUT"} else "warning",
        title="Order execution failed",
        message="An order execution reached a failed terminal state.",
        metadata={
            "component": "order_execution",
            "status": safe_status,
            "failure_type": safe_failure_type,
        },
    )


def build_rate_limit_alert(
    *,
    exchange_name: str,
    scope: str,
    request_category: str,
    retry_after_seconds: int,
) -> object:
    from app.services.external_alerts import ExternalAlertEvent

    safe_exchange_name = _safe_exchange_name(exchange_name)
    safe_scope = _safe_rate_limit_scope(scope)
    safe_request_category = _safe_rate_limit_request_category(request_category)
    safe_retry_after_seconds = str(max(1, min(retry_after_seconds, 3_600)))
    return ExternalAlertEvent(
        severity="warning",
        title="Rate limit protection triggered",
        message="Runtime rate-limit protection blocked an outbound exchange request.",
        metadata={
            "component": "rate_limit",
            "exchange": safe_exchange_name,
            "scope": safe_scope,
            "request_category": safe_request_category,
            "retry_after_seconds": safe_retry_after_seconds,
        },
    )


def maybe_send_dependency_health_alert(
    checks: dict[str, str],
    config: object,
    *,
    now_seconds: int,
    throttle_seconds: int = DEFAULT_DEPENDENCY_ALERT_THROTTLE_SECONDS,
    dispatch_state: dict[str, int] | None = None,
    transports: object | None = None,
) -> tuple[object, ...]:
    event = build_dependency_health_alert(checks)
    if event is None:
        return ()

    state = dispatch_state if dispatch_state is not None else {}
    if _is_throttled(
        state=state,
        key=DEPENDENCY_HEALTH_ALERT_KEY,
        now_seconds=now_seconds,
        throttle_seconds=throttle_seconds,
    ):
        return ()

    from app.services.external_alerts import send_external_alert

    results = send_external_alert(config, event, transports)
    state[DEPENDENCY_HEALTH_ALERT_KEY] = now_seconds
    return results


def maybe_send_order_failure_alert(
    *,
    status: str,
    failure_type: str,
    config: object,
    now_seconds: int,
    throttle_seconds: int = DEFAULT_ORDER_FAILURE_ALERT_THROTTLE_SECONDS,
    dispatch_state: dict[str, int] | None = None,
    transports: object | None = None,
) -> tuple[object, ...]:
    event = build_order_failure_alert(status=status, failure_type=failure_type)
    if event is None:
        return ()

    safe_status = str(event.metadata["status"])
    safe_failure_type = str(event.metadata["failure_type"])
    key = f"{ORDER_FAILURE_ALERT_KEY_PREFIX}:{safe_status}:{safe_failure_type}"
    state = dispatch_state if dispatch_state is not None else {}
    if _is_throttled(
        state=state,
        key=key,
        now_seconds=now_seconds,
        throttle_seconds=throttle_seconds,
    ):
        return ()

    from app.services.external_alerts import send_external_alert

    results = send_external_alert(config, event, transports)
    state[key] = now_seconds
    return results


def maybe_send_rate_limit_alert(
    *,
    exchange_name: str,
    scope: str,
    request_category: str,
    retry_after_seconds: int,
    config: object,
    now_seconds: int,
    throttle_seconds: int = DEFAULT_RATE_LIMIT_ALERT_THROTTLE_SECONDS,
    dispatch_state: dict[str, int] | None = None,
    transports: object | None = None,
) -> tuple[object, ...]:
    event = build_rate_limit_alert(
        exchange_name=exchange_name,
        scope=scope,
        request_category=request_category,
        retry_after_seconds=retry_after_seconds,
    )
    key = ":".join(
        (
            RATE_LIMIT_ALERT_KEY_PREFIX,
            str(event.metadata["exchange"]),
            str(event.metadata["scope"]),
            str(event.metadata["request_category"]),
        )
    )
    state = dispatch_state if dispatch_state is not None else {}
    if _is_throttled(
        state=state,
        key=key,
        now_seconds=now_seconds,
        throttle_seconds=throttle_seconds,
    ):
        return ()

    from app.services.external_alerts import send_external_alert

    results = send_external_alert(config, event, transports)
    state[key] = now_seconds
    return results


def _is_throttled(
    state: dict[str, int],
    key: str,
    now_seconds: int,
    throttle_seconds: int,
) -> bool:
    if throttle_seconds <= 0:
        return False
    last_sent_at = state.get(key)
    if last_sent_at is None:
        return False
    return now_seconds - last_sent_at < throttle_seconds


def _safe_state(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in SAFE_DEPENDENCY_STATES:
        return normalized
    return "unknown"


def _safe_exchange_name(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in SAFE_EXCHANGE_NAMES:
        return normalized
    return "unknown"


def _safe_order_failure_status(value: str) -> str | None:
    normalized = value.strip().upper()
    if normalized in SAFE_ORDER_FAILURE_STATUSES:
        return normalized
    return None


def _safe_order_failure_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in SAFE_ORDER_FAILURE_TYPES:
        return normalized
    return "unknown"


def _safe_rate_limit_scope(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in SAFE_RATE_LIMIT_SCOPES:
        return normalized
    return "unknown"


def _safe_rate_limit_request_category(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in SAFE_RATE_LIMIT_REQUEST_CATEGORIES:
        return normalized
    return "unknown"
