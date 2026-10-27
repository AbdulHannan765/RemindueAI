import os
import hmac
import hashlib


_key = os.environ.get("BLIND_INDEX_KEY")

if not _key:
    raise RuntimeError(
        "BLIND_INDEX_KEY is missing from environment variables"
    )

_key_bytes = _key.encode("utf-8")


def create_blind_index(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip().lower()

    return hmac.new(
        _key_bytes,
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()