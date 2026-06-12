import dataclasses


@dataclasses.dataclass(frozen=True)
class DependencyHealthMonitorConfig:
    enabled: bool = False
    interval_seconds: int = 60
    throttle_seconds: int = 300


@dataclasses.dataclass(frozen=True)
class DependencyHealthMonitorPlan:
    enabled: bool
    interval_seconds: int
    throttle_seconds: int
    validation_errors: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.enabled and not self.validation_errors


def build_dependency_health_monitor_plan(
    config: DependencyHealthMonitorConfig,
) -> DependencyHealthMonitorPlan:
    validation_errors: list[str] = []
    if config.interval_seconds <= 0:
        validation_errors.append("dependency health monitor interval must be positive")
    if config.throttle_seconds < 0:
        validation_errors.append("dependency health alert throttle must not be negative")

    return DependencyHealthMonitorPlan(
        enabled=config.enabled,
        interval_seconds=config.interval_seconds,
        throttle_seconds=config.throttle_seconds,
        validation_errors=tuple(validation_errors),
    )


def run_dependency_health_monitor_tick(
    checks_provider,
    alert_config: object,
    monitor_config: DependencyHealthMonitorConfig,
    *,
    now_seconds: int,
    dispatch_state: dict[str, int] | None = None,
    transports: object | None = None,
) -> tuple[object, ...]:
    plan = build_dependency_health_monitor_plan(monitor_config)
    if not plan.ready:
        return ()

    checks = checks_provider()

    from app.services.operational_alerts import maybe_send_dependency_health_alert

    return maybe_send_dependency_health_alert(
        checks,
        alert_config,
        now_seconds=now_seconds,
        throttle_seconds=plan.throttle_seconds,
        dispatch_state=dispatch_state,
        transports=transports,
    )
