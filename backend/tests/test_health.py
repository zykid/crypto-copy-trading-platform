import asyncio

from fastapi.testclient import TestClient

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


def test_frontend_cors_preflight_is_allowed() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://192.168.2.42:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://192.168.2.42:3000"
