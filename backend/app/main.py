from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(health_router, prefix="/api/v1", tags=["system"])
    return app


app = create_app()
