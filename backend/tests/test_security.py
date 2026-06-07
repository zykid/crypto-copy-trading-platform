from datetime import timedelta

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_not_plaintext_and_verifies() -> None:
    password_hash = hash_password("very-strong-password")

    assert password_hash != "very-strong-password"
    assert verify_password("very-strong-password", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_access_token_roundtrip_and_expiry() -> None:
    token = create_access_token("user-123")
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "user-123"

    expired = create_access_token("user-123", expires_delta=timedelta(seconds=-1))
    assert decode_access_token(expired) is None
