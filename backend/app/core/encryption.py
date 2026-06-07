import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_secret: str) -> str:
    return _fernet().decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")


def _fernet() -> Fernet:
    key = hashlib.sha256(settings.secret_encryption_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))
