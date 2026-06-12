from .external_alerts import ExternalAlertEvent


SAFE_DEPENDENCY_NAMES = frozenset({"database", "redis", "backend", "frontend", "caddy"})
SAFE_DEPENDENCY_STATES = frozenset({"ok", "degraded", "unavailable", "unknown"})


def build_dependency_health_alert(
    checks: dict[str, str],
) -> ExternalAlertEvent | None:
    status = _safe_state(checks.get("status", "unknown"))
    if status == "ok":
        return None

    affected = tuple(
        name
        for name, state in sorted(checks.items())
        if name in SAFE_DEPENDENCY_NAMES and _safe_state(state) != "ok"
    )
    affected_value = ",".join(affected) if affected else "unknown"

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


def _safe_state(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in SAFE_DEPENDENCY_STATES:
        return normalized
    return "unknown"
