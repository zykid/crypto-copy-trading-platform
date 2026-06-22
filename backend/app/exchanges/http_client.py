import base64
import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.db.models.exchange_account import ExchangeName


class ExchangeSecurityType(StrEnum):
    PUBLIC = "PUBLIC"
    SIGNED = "SIGNED"
    OKX_DEMO_SIGNED = "OKX_DEMO_SIGNED"


class ExchangeHttpRequestError(RuntimeError):
    def __init__(
        self,
        *,
        failure_type: str,
        status_code: int | None = None,
        exchange_code: str | None = None,
    ) -> None:
        super().__init__("exchange HTTP request failed")
        self.failure_type = failure_type
        self.status_code = status_code
        self.exchange_code = exchange_code


@dataclass(frozen=True)
class ExchangeCredentials:
    api_key: str
    api_secret: str
    passphrase: str | None = None


@dataclass(frozen=True)
class PreparedExchangeRequest:
    method: str
    url: str
    path: str
    params: dict[str, str]
    headers: dict[str, str]
    body: dict[str, Any] | None = None


class ExchangeHttpTransport(Protocol):
    def request(self, prepared: PreparedExchangeRequest) -> dict[str, Any]:
        raise NotImplementedError


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


class UrllibExchangeHttpTransport:
    def request(self, prepared: PreparedExchangeRequest) -> dict[str, Any]:
        query = _canonical_query(prepared.params)
        url = f"{prepared.url}?{query}" if query else prepared.url
        body = _json_body(prepared.body).encode("utf-8") if prepared.body is not None else None
        headers = {"User-Agent": "crypto-copy-trading-platform/0.1", **prepared.headers}
        request = Request(url=url, data=body, headers=headers, method=prepared.method)
        try:
            with urlopen(request, timeout=10) as response:  # noqa: S310
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            exchange_code = _read_exchange_error_code(exc)
            raise ExchangeHttpRequestError(
                failure_type=_http_failure_type(exc.code),
                status_code=exc.code,
                exchange_code=exchange_code,
            ) from exc
        except Exception as exc:
            raise ExchangeHttpRequestError(failure_type="transport_error") from exc
        return json.loads(payload) if payload else {}


class SignedExchangeHttpClient:
    def __init__(
        self,
        *,
        exchange_name: ExchangeName,
        rest_base_url: str,
        transport: ExchangeHttpTransport | None = None,
        timestamp_ms_factory: Callable[[], int] | None = None,
        iso_timestamp_factory: Callable[[], str] | None = None,
        recv_window: str = "5000",
    ) -> None:
        self.exchange_name = exchange_name
        self.rest_base_url = rest_base_url.rstrip("/")
        self.transport = transport or UrllibExchangeHttpTransport()
        self.timestamp_ms_factory = timestamp_ms_factory or _default_timestamp_ms
        self.iso_timestamp_factory = iso_timestamp_factory or _default_iso_timestamp
        self.recv_window = recv_window

    def get_public(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        prepared = self.prepare_public_request(path, params=params)
        return self.transport.request(prepared)

    def get_private(
        self,
        path: str,
        *,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None = None,
        security_type: ExchangeSecurityType = ExchangeSecurityType.SIGNED,
    ) -> dict[str, Any]:
        prepared = self.prepare_private_request(
            path,
            credentials=credentials,
            params=params,
            security_type=security_type,
        )
        return self.transport.request(prepared)

    def post_private(
        self,
        path: str,
        *,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        security_type: ExchangeSecurityType = ExchangeSecurityType.SIGNED,
    ) -> dict[str, Any]:
        prepared = self.prepare_private_post_request(
            path,
            credentials=credentials,
            params=params,
            body=body,
            security_type=security_type,
        )
        return self.transport.request(prepared)

    def execute_prepared_request(self, prepared: PreparedExchangeRequest) -> dict[str, Any]:
        return self.transport.request(prepared)

    def prepare_public_request(
        self, path: str, params: dict[str, str] | None = None
    ) -> PreparedExchangeRequest:
        return PreparedExchangeRequest(
            method="GET",
            url=f"{self.rest_base_url}{path}",
            path=path,
            params=dict(params or {}),
            headers={},
        )

    def prepare_private_request(
        self,
        path: str,
        *,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None = None,
        security_type: ExchangeSecurityType = ExchangeSecurityType.SIGNED,
    ) -> PreparedExchangeRequest:
        return self._prepare_private_request(
            "GET",
            path,
            credentials=credentials,
            params=params,
            body=None,
            security_type=security_type,
        )

    def prepare_private_post_request(
        self,
        path: str,
        *,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        security_type: ExchangeSecurityType = ExchangeSecurityType.SIGNED,
    ) -> PreparedExchangeRequest:
        return self._prepare_private_request(
            "POST",
            path,
            credentials=credentials,
            params=params,
            body=body,
            security_type=security_type,
        )

    def _prepare_private_request(
        self,
        method: str,
        path: str,
        *,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None,
        body: dict[str, Any] | None,
        security_type: ExchangeSecurityType,
    ) -> PreparedExchangeRequest:
        if self.exchange_name == ExchangeName.BINANCE:
            return self._prepare_binance_request(method, path, credentials, params)
        if self.exchange_name == ExchangeName.BYBIT:
            return self._prepare_bybit_request(method, path, credentials, params, body)
        if self.exchange_name == ExchangeName.OKX:
            return self._prepare_okx_request(method, path, credentials, params, body, security_type)
        raise ValueError(f"signed HTTP client is not supported for {self.exchange_name}")

    def _prepare_binance_request(
        self,
        method: str,
        path: str,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None,
    ) -> PreparedExchangeRequest:
        signed_params = dict(params or {})
        signed_params["timestamp"] = str(self.timestamp_ms_factory())
        signed_params["recvWindow"] = self.recv_window
        query = _canonical_query(signed_params)
        signed_params["signature"] = _hmac_sha256_hex(credentials.api_secret, query)
        return PreparedExchangeRequest(
            method=method,
            url=f"{self.rest_base_url}{path}",
            path=path,
            params=signed_params,
            headers={"X-MBX-APIKEY": credentials.api_key},
        )

    def _prepare_bybit_request(
        self,
        method: str,
        path: str,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None,
        body: dict[str, Any] | None,
    ) -> PreparedExchangeRequest:
        request_params = dict(params or {})
        request_body = dict(body or {}) if method == "POST" else None
        timestamp = str(self.timestamp_ms_factory())
        payload_data = (
            _json_body(request_body)
            if request_body is not None
            else _canonical_query(request_params)
        )
        payload = f"{timestamp}{credentials.api_key}{self.recv_window}{payload_data}"
        headers = {
            "X-BAPI-API-KEY": credentials.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": self.recv_window,
            "X-BAPI-SIGN": _hmac_sha256_hex(credentials.api_secret, payload),
        }
        if request_body is not None:
            headers["Content-Type"] = "application/json"
        return PreparedExchangeRequest(
            method=method,
            url=f"{self.rest_base_url}{path}",
            path=path,
            params=request_params,
            headers=headers,
            body=request_body,
        )

    def _prepare_okx_request(
        self,
        method: str,
        path: str,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None,
        body: dict[str, Any] | None,
        security_type: ExchangeSecurityType,
    ) -> PreparedExchangeRequest:
        if credentials.passphrase is None:
            raise ValueError("OKX signed requests require an API passphrase")
        request_params = dict(params or {})
        request_body = dict(body or {}) if method == "POST" else None
        timestamp = self.iso_timestamp_factory()
        path_with_query = path
        query = _canonical_query(request_params)
        if query:
            path_with_query = f"{path}?{query}"
        body_payload = _json_body(request_body) if request_body is not None else ""
        signature_payload = f"{timestamp}{method}{path_with_query}{body_payload}"
        headers = {
            "OK-ACCESS-KEY": credentials.api_key,
            "OK-ACCESS-SIGN": _hmac_sha256_base64(credentials.api_secret, signature_payload),
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": credentials.passphrase,
        }
        if request_body is not None:
            headers["Content-Type"] = "application/json"
        if security_type == ExchangeSecurityType.OKX_DEMO_SIGNED:
            headers["x-simulated-trading"] = "1"
        return PreparedExchangeRequest(
            method=method,
            url=f"{self.rest_base_url}{path}",
            path=path,
            params=request_params,
            headers=headers,
            body=request_body,
        )


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


def _canonical_query(params: dict[str, str]) -> str:
    return urlencode(sorted(params.items()))


def _json_body(body: dict[str, Any] | None) -> str:
    return json.dumps(body or {}, separators=(",", ":"), sort_keys=True)


def _hmac_sha256_hex(secret: str, payload: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _hmac_sha256_base64(secret: str, payload: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _default_timestamp_ms() -> int:
    from time import time

    return int(time() * 1000)


def _default_iso_timestamp() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _read_exchange_error_code(exc: HTTPError) -> str | None:
    try:
        payload = json.loads(exc.read(4096).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    code = payload.get("code")
    if code is None:
        return None
    value = str(code)
    return value[:40] if value else None


def _http_failure_type(status_code: int) -> str:
    if status_code in {401, 403}:
        return "authentication_failed"
    if status_code == 429:
        return "rate_limited"
    if status_code >= 500:
        return "exchange_unavailable"
    return "request_rejected"
