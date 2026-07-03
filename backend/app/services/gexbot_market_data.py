import json
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

_TICKER_RE = re.compile(r"^[A-Z0-9._-]{1,24}$")
_CATEGORY_RE = re.compile(r"^[a-z0-9_]{1,64}$")
_SUPPORTED_PACKAGES = {"classic", "state"}


class GexbotMarketDataError(RuntimeError):
    def __init__(self, *, failure_type: str, status_code: int | None = None) -> None:
        super().__init__("gexbot market data request failed")
        self.failure_type = failure_type
        self.status_code = status_code


class GexbotConfigurationError(RuntimeError):
    pass


class GexbotValidationError(ValueError):
    pass


class GexbotTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class UrllibGexbotTransport:
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        request = Request(url=url, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            raise GexbotMarketDataError(
                failure_type=_http_failure_type(exc.code),
                status_code=exc.code,
            ) from exc
        except (OSError, URLError) as exc:
            raise GexbotMarketDataError(failure_type="transport_error") from exc
        return json.loads(payload) if payload else {}


class GexbotMarketDataClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        timeout_seconds: float = 5.0,
        transport: GexbotTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.transport = transport or UrllibGexbotTransport()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def list_tickers(self) -> dict[str, Any]:
        return self._get("/tickers", auth_required=False)

    def get_package_category(self, *, ticker: str, package: str, category: str) -> dict[str, Any]:
        validated_ticker = _validate_ticker(ticker)
        validated_package = _validate_package(package)
        validated_category = _validate_category(category)
        return self._get(
            f"/{quote(validated_ticker)}/{validated_package}/{quote(validated_category)}",
            auth_required=True,
        )

    def get_orderflow(self, *, ticker: str) -> dict[str, Any]:
        validated_ticker = _validate_ticker(ticker)
        return self._get(f"/{quote(validated_ticker)}/orderflow/orderflow", auth_required=True)

    def _get(self, path: str, *, auth_required: bool) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "crypto-copy-trading-platform/0.1",
        }
        if auth_required:
            headers["Authorization"] = _authorization_header(self.api_key)
        return self.transport.request(
            method="GET",
            url=f"{self.base_url}{path}",
            headers=headers,
            timeout_seconds=self.timeout_seconds,
        )


def _authorization_header(api_key: str) -> str:
    key = api_key.strip()
    if not key:
        raise GexbotConfigurationError("GEXBot API key is not configured")
    if key.lower().startswith("bearer "):
        return key
    if key.startswith("gexbot_custom_"):
        return f"Bearer {key}"
    return f"Bearer gexbot_custom_{key}"


def _validate_ticker(value: str) -> str:
    normalized = value.strip().upper()
    if not _TICKER_RE.fullmatch(normalized):
        raise GexbotValidationError("invalid GEXBot ticker")
    return normalized


def _validate_category(value: str) -> str:
    normalized = value.strip().lower()
    if not _CATEGORY_RE.fullmatch(normalized):
        raise GexbotValidationError("invalid GEXBot category")
    return normalized


def _validate_package(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in _SUPPORTED_PACKAGES:
        raise GexbotValidationError("invalid GEXBot package")
    return normalized


def _http_failure_type(status_code: int) -> str:
    if status_code in {401, 403}:
        return "authentication_failed"
    if status_code == 429:
        return "rate_limited"
    if status_code >= 500:
        return "provider_unavailable"
    return "request_rejected"
