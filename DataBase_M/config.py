
import os

from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()


# --------------------------------------------------
# TELEGRAM CONFIGURATION
# --------------------------------------------------

TELEGRAM_API_ID = int(os.environ["TELEGRAM_API_ID"])
TELEGRAM_API_HASH = os.environ["TELEGRAM_API_HASH"]


# --------------------------------------------------
# DATABASE AND JWT CONFIGURATION
# --------------------------------------------------

DATABASE_URL = os.environ["DATABASE_URL"]
SECRET_KEY = os.environ["SECRET_KEY"]


# --------------------------------------------------
# GMAIL CONFIGURATION
# --------------------------------------------------

GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]

GMAIL_REDIRECT_URI = os.environ["GMAIL_REDIRECT_URI"]

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]



# ENCRYPTION CONFIGURATION



# ENCRYPTION CONFIGURATION

cipher = Fernet(
    os.environ["SESSION_ENCRYPTION_KEY"].encode("utf-8")
)


def encrypt_session(session: str | bytes) -> str:
    """
    Encrypt either a string or bytes.
    Always return encrypted string for PostgreSQL VARCHAR.
    """

    if isinstance(session, str):
        session = session.encode("utf-8")

    encrypted = cipher.encrypt(session)

    return encrypted.decode("utf-8")


def decrypt_session(encrypted_session: str | bytes) -> bytes:
    """
    Decrypt encrypted string or bytes.
    Always return original bytes.
    """

    if isinstance(encrypted_session, str):
        encrypted_session = encrypted_session.encode("utf-8")

    return cipher.decrypt(encrypted_session)
