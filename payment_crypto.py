import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet():
    secret = os.environ.get("SECRET_KEY", "change-this-secret-key")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value):
    value = (value or "").strip()
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value):
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""


def secret_configured(value):
    return bool((value or "").strip())
