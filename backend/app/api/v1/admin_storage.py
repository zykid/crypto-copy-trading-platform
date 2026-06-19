from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_super_admin_user
from app.core.config import settings
from app.db.models.user import User
from app.schemas.user import StorageLocationResponse
from app.services.storage_locations import (
    StorageLocationConfigurationError,
    parse_storage_locations,
)

router = APIRouter()


@router.get("/locations", response_model=list[StorageLocationResponse])
def list_storage_locations(
    _super_admin: User = Depends(get_current_super_admin_user),
) -> list[StorageLocationResponse]:
    try:
        locations = parse_storage_locations(
            settings.storage_location_allowlist,
            current_path=settings.trading_data_root,
        )
    except StorageLocationConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="storage location configuration is invalid",
        ) from exc

    return [StorageLocationResponse(**location.__dict__) for location in locations]
