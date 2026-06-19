import pytest
from fastapi import HTTPException

from app.api.deps import get_current_admin_user, get_current_super_admin_user
from app.db.models.user import User, UserRole
from app.main import app
from app.services.storage_locations import (
    StorageLocationConfigurationError,
    parse_storage_locations,
)


def make_user(role: UserRole) -> User:
    return User(
        email=f"{role.value}@example.com",
        username=role.value,
        password_hash="not-used",
        role=role,
    )


def test_super_admin_inherits_admin_read_permissions() -> None:
    user = make_user(UserRole.SUPER_ADMIN)

    assert get_current_admin_user(user) is user


def test_only_super_admin_passes_storage_dependency() -> None:
    super_admin = make_user(UserRole.SUPER_ADMIN)
    admin = make_user(UserRole.ADMIN)

    assert get_current_super_admin_user(super_admin) is super_admin
    with pytest.raises(HTTPException) as exc_info:
        get_current_super_admin_user(admin)

    assert exc_info.value.status_code == 403


def test_storage_allowlist_marks_current_location() -> None:
    locations = parse_storage_locations(
        "test_storage=/home/zykid/trading-storage-test,"
        "mechanical=/mnt/trading-data",
        current_path="/home/zykid/trading-storage-test",
    )

    assert [location.id for location in locations] == [
        "test_storage",
        "mechanical",
    ]
    assert locations[0].is_current is True
    assert locations[1].is_current is False
    assert locations[1].label == "Mechanical"


@pytest.mark.parametrize(
    "allowlist",
    [
        "bad id=/mnt/data",
        "root=/",
        "relative=var/lib/data",
        "escape=/mnt/data/../other",
        "same=/mnt/data,duplicate=/mnt/data",
        "same=/mnt/data,same=/mnt/other",
    ],
)
def test_storage_allowlist_rejects_unsafe_or_duplicate_entries(
    allowlist: str,
) -> None:
    with pytest.raises(StorageLocationConfigurationError):
        parse_storage_locations(allowlist)


def test_admin_storage_route_is_registered() -> None:
    assert "/api/v1/admin/storage/locations" in app.openapi()["paths"]
