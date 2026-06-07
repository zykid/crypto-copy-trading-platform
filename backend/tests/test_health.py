import asyncio

from app.api.v1.health import health_check
from app.main import app


def test_health_check_returns_service_status() -> None:
    response = asyncio.run(health_check())

    assert response == {
        "status": "ok",
        "service": "Multi-Tenant Crypto Trading Platform",
        "version": "0.1.0",
        "environment": "development",
    }


def test_health_route_is_registered() -> None:
    route_paths = {route.path for route in app.routes}

    assert "/api/v1/health" in route_paths
