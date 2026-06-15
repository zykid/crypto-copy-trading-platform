import asyncio

from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import health_check
from app.core.config import settings
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
    assert "/api/v1/health" in app.openapi()["paths"]


def test_frontend_cors_origin_is_configured() -> None:
    assert "http://192.168.2.42:3000" in settings.cors_origins


def test_cors_middleware_is_registered() -> None:
    cors_middleware = [item for item in app.user_middleware if item.cls is CORSMiddleware]

    assert cors_middleware
    assert "http://192.168.2.42:3000" in cors_middleware[0].kwargs["allow_origins"]
    assert "POST" in cors_middleware[0].kwargs["allow_methods"]
    assert "Authorization" in cors_middleware[0].kwargs["allow_headers"]
