import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def get_fernet():
    key = os.getenv("QDRANT_PAYLOAD_ENCRYPTION_KEY")

    if not key:
        raise RuntimeError(
            "QDRANT_PAYLOAD_ENCRYPTION_KEY is missing"
        )

    return Fernet(key.encode("utf-8"))


def encrypt_payload(value):
    if value is None:
        return None

    if not isinstance(value, str):
        value = str(value)

    return get_fernet().encrypt(
        value.encode("utf-8")
    ).decode("utf-8")


def decrypt_payload(value):
    if value is None:
        return None

    try:
        return get_fernet().decrypt(
            value.encode("utf-8")
        ).decode("utf-8")

    except InvalidToken as exc:
        raise ValueError(
            "Unable to decrypt Qdrant payload. "
            "Check the encryption key."
        ) from exc