import os

from cryptography.fernet import Fernet, InvalidToken


_key = os.environ.get("NOTIFICATION_ENCRYPTION_KEY")

if not _key:
    raise RuntimeError(
        "NOTIFICATION_ENCRYPTION_KEY is missing from environment variables"
    )

try:
    _fernet = Fernet(_key.encode("utf-8"))
except Exception as exc:
    raise RuntimeError(
        "NOTIFICATION_ENCRYPTION_KEY is invalid. "
        "Generate a valid Fernet key."
    ) from exc


def encrypt_value(value: str | None) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError("encrypt_value expects a string or None")

    return _fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str | None) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError("decrypt_value expects a string or None")

    try:
        return _fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Could not decrypt database value. Check the encryption key "
            "and whether this row has already been encrypted."
        ) from exc