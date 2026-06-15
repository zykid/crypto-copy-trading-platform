from app.api.metrics import METRICS_CONTENT_TYPE, build_metrics_text
from app.main import app


def app_route_paths() -> set[str]:
    return {route.path for route in app.routes if hasattr(route, "path")}


def test_metrics_text_exposes_only_safe_operational_values() -> None:
    metrics_text = build_metrics_text()

    assert "trading_app_info" in metrics_text
    assert "trading_real_trading_enabled 0" in metrics_text
    assert "trading_testnet_adapters_enabled 0" in metrics_text
    assert "api_key" not in metrics_text.lower()
    assert "secret" not in metrics_text.lower()
    assert "user_id" not in metrics_text.lower()
    assert "exchange_account" not in metrics_text.lower()
    assert "balance" not in metrics_text.lower()
    assert "position" not in metrics_text.lower()
    assert metrics_text.endswith("\n")


def test_metrics_route_is_registered_outside_api_prefix() -> None:
    assert "/metrics" in app_route_paths()


def test_metrics_content_type_is_prometheus_text_format() -> None:
    assert METRICS_CONTENT_TYPE == "text/plain; version=0.0.4; charset=utf-8"
