from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.exchange_accounts import router as exchange_accounts_router
from app.api.v1.health import router as health_router
from app.api.v1.permissions import router as permissions_router
from app.api.v1.users import router as users_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(health_router, prefix="/api/v1", tags=["system"])
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
    app.include_router(permissions_router, prefix="/api/v1/permissions", tags=["permissions"])
    app.include_router(
        exchange_accounts_router,
        prefix="/api/v1/exchange-accounts",
        tags=["exchange-accounts"],
    )
    return app


app = create_app()
