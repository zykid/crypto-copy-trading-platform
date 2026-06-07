from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.permission import PermissionCreate, PermissionResponse, PermissionUpdate
from app.services.permissions import (
    create_permission,
    delete_permission,
    get_owned_permission,
    list_permissions_for_owner,
    update_permission,
)

router = APIRouter()


@router.get("", response_model=list[PermissionResponse])
def list_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_permissions_for_owner(db, owner_user_id=current_user.id)


@router.post("", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
def add_permission(
    payload: PermissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.grantee_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cannot share with self",
        )
    return create_permission(
        db,
        owner_user_id=current_user.id,
        data=payload.model_dump(),
    )


@router.patch("/{permission_id}", response_model=PermissionResponse)
def patch_permission(
    permission_id: str,
    payload: PermissionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permission = get_owned_permission(
        db,
        owner_user_id=current_user.id,
        permission_id=permission_id,
    )
    if permission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="permission not found")
    return update_permission(permission, payload.model_dump(exclude_unset=True), db)


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_permission(
    permission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permission = get_owned_permission(
        db,
        owner_user_id=current_user.id,
        permission_id=permission_id,
    )
    if permission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="permission not found")
    delete_permission(permission, db)
