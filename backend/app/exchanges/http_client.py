from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class ExchangeSecurityType(StrEnum):
    PUBLIC = "PUBLIC"
    SIGNED = "SIGNED"
    OKX_DEMO_SIGNED = "OKX_DEMO_SIGNED"


@dataclass(frozen=True)
class ExchangeCredentials:
    api_key: str
    api_secret: str
    passphrase: str | None = None


class ExchangeHttpClient(Protocol):
    def get_public(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def get_private(
        self,
        path: str,
        *,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None = None,
        security_type: ExchangeSecurityType = ExchangeSecurityType.SIGNED,
    ) -> dict[str, Any]:
        raise NotImplementedError


class NoopExchangeHttpClient:
    def get_public(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        raise RuntimeError("exchange HTTP client is not configured")

    def get_private(
        self,
        path: str,
        *,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None = None,
        security_type: ExchangeSecurityType = ExchangeSecurityType.SIGNED,
    ) -> dict[str, Any]:
        raise RuntimeError("exchange HTTP client is not configured")
