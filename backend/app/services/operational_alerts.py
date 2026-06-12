SAFE_DEPENDENCY_NAMES = frozenset({"database", "redis", "backend", "frontend", "caddy"})
SAFE_DEPENDENCY_STATES = frozenset({"ok", "degraded", "unavailable", "unknown"})
DEPENDENCY_HEALTH_ALERT_KEY = "dependency_health"
DEFAULT_DEPENDENCY_ALERT_THROTTLE_SECONDS = 300


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
