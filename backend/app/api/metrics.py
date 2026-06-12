from collections.abc import Mapping

from fastapi import APIRouter, Response

from app.core.config import settings

router = APIRouter()

METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(values: Mapping[str, str]) -> str:
    return ",".join(f'{key}="{_escape_label_value(value)}"' for key, value in values.items())


def build_metrics_text() -> str:
    app_labels = _labels(
        {
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        }
    )

    lines = [
        "# HELP trading_app_info Application build and environment information.",
        "# TYPE trading_app_info gauge",
        f"trading_app_info{{{app_labels}}} 1",
        "# HELP trading_real_trading_enabled Real trading enablement flag.",
        "# TYPE trading_real_trading_enabled gauge",
        "trading_real_trading_enabled 0",
        "# HELP trading_testnet_adapters_enabled Testnet adapter enablement flag.",
        "# TYPE trading_testnet_adapters_enabled gauge",
        f"trading_testnet_adapters_enabled {int(settings.testnet_adapters_enabled)}",
        "",
    ]
    return "\n".join(lines)


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=build_metrics_text(), media_type=METRICS_CONTENT_TYPE)
