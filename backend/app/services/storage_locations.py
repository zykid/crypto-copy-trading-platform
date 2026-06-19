import re
from dataclasses import dataclass
from pathlib import PurePosixPath

_STORAGE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


class StorageLocationConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class StorageLocation:
    id: str
    label: str
    path: str
    is_current: bool


def _normalize_absolute_path(raw_path: str) -> str:
    path = PurePosixPath(raw_path)
    if not path.is_absolute() or str(path) == "/" or ".." in path.parts:
        raise StorageLocationConfigurationError("storage path must be absolute and scoped")
    return str(path)


def parse_storage_locations(
    allowlist: str,
    *,
    current_path: str = "",
) -> tuple[StorageLocation, ...]:
    normalized_current = (
        _normalize_absolute_path(current_path) if current_path.strip() else None
    )
    locations: list[StorageLocation] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()

    for raw_entry in allowlist.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue

        location_id, separator, raw_path = entry.partition("=")
        location_id = location_id.strip()
        raw_path = raw_path.strip()
        if separator != "=" or not _STORAGE_ID_PATTERN.fullmatch(location_id):
            raise StorageLocationConfigurationError("invalid storage location identifier")
        if not raw_path:
            raise StorageLocationConfigurationError("storage location path is required")

        path = _normalize_absolute_path(raw_path)
        if location_id in seen_ids or path in seen_paths:
            raise StorageLocationConfigurationError("duplicate storage location")

        seen_ids.add(location_id)
        seen_paths.add(path)
        locations.append(
            StorageLocation(
                id=location_id,
                label=location_id.replace("_", " ").replace("-", " ").title(),
                path=path,
                is_current=path == normalized_current,
            )
        )

    return tuple(locations)
