import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings

_HASH_ITERATIONS = 390_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _HASH_ITERATIONS)
    return f"pbkdf2_sha256${_HASH_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        _b64decode(salt),
        int(iterations),
    )
    return hmac.compare_digest(_b64encode(digest), expected)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expires_at = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.jwt_expires_minutes))
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "exp": int(expires_at.timestamp())}
    signing_input = f"{_json_b64(header)}.{_json_b64(payload)}"
    signature = _sign(signing_input)
    return f"{signing_input}.{signature}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        header_b64, payload_b64, signature = token.split(".", 2)
    except ValueError:
        return None
    signing_input = f"{header_b64}.{payload_b64}"
    if not hmac.compare_digest(_sign(signing_input), signature):
        return None
    payload = json.loads(_b64decode(payload_b64))
    expires_at = int(payload.get("exp", 0))
    if expires_at < int(datetime.now(UTC).timestamp()):
        return None
    return payload


def _sign(value: str) -> str:
    digest = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64encode(digest)


def _json_b64(value: dict[str, Any]) -> str:
    return _b64encode(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
