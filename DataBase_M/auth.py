
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from DataBase_M.config import SECRET_KEY




# PASSWORD HASHING
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a user's password using Argon2."""
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Verify a password against its stored hash."""
    return password_hash.verify(
        plain_password,
        hashed_password,
    )


# JWT CONFIGURATION
ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


# CREATE ACCESS TOKEN


def create_access_token(user_id: str) -> str:

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": user_id,
        "exp": expire,
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return token
