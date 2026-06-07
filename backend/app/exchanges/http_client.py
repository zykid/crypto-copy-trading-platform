from typing import Any, Protocol


class ExchangeHttpClient(Protocol):
    def get_public(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        raise NotImplementedError


class NoopExchangeHttpClient:
    def get_public(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        raise RuntimeError("exchange HTTP client is not configured")
