from fastapi import APIRouter, HTTPException, status
from redis import Redis
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/health/dependencies")
def dependency_health_check() -> dict[str, str]:
    checks = {
        "status": "ok",
        "database": "ok",
        "redis": "ok",
    }

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        checks["status"] = "degraded"
        checks["database"] = "unavailable"

    redis_client = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
        decode_responses=True,
    )
    try:
        redis_client.ping()
    except Exception:
        checks["status"] = "degraded"
        checks["redis"] = "unavailable"
    finally:
        redis_client.close()

    if checks["status"] != "ok":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=checks)
    return checks
