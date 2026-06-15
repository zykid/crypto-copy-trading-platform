from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.metrics import router as metrics_router
from app.api.v1.admin_observability import router as admin_observability_router
from app.api.v1.auth import router as auth_router
from app.api.v1.exchange_accounts import router as exchange_accounts_router
from app.api.v1.health import router as health_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.orders import router as orders_router
from app.api.v1.permissions import router as permissions_router
from app.api.v1.positions import router as positions_router
from app.api.v1.risk_settings import router as risk_settings_router
from app.api.v1.signals import router as signals_router
from app.api.v1.users import router as users_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Authorization", "Content-Type"],
    )
    app.include_router(metrics_router, tags=["metrics"])
    app.include_router(health_router, prefix="/api/v1", tags=["system"])
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
    app.include_router(permissions_router, prefix="/api/v1/permissions", tags=["permissions"])
    app.include_router(
        exchange_accounts_router,
        prefix="/api/v1/exchange-accounts",
        tags=["exchange-accounts"],
    )
    app.include_router(signals_router, prefix="/api/v1/signals", tags=["signals"])
    app.include_router(orders_router, prefix="/api/v1/orders", tags=["orders"])
    app.include_router(positions_router, prefix="/api/v1/positions", tags=["positions"])
    app.include_router(
        risk_settings_router,
        prefix="/api/v1/risk-settings",
        tags=["risk-settings"],
    )
    app.include_router(
        notifications_router,
        prefix="/api/v1/notifications",
        tags=["notifications"],
    )
    app.include_router(
        admin_observability_router,
        prefix="/api/v1/admin/observability",
        tags=["admin-observability"],
    )
    return app


app = create_app()
