
import uuid

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PasswordHashInvalidError,
)
from security_and_privacy import create_blind_index
from sqlalchemy import select

from DataBase_M.config import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    encrypt_session,
)

from DataBase_M.database import SessionLocal
from DataBase_M.tables import TelegramConnection




pending_logins = {}



async def start_telegram_login(user_id, phone_number):

    client = TelegramClient(
        StringSession(),
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
    )

    await client.connect()

    try:
        sent_code = await client.send_code_request(phone_number)

        login_id = str(uuid.uuid4())

        pending_logins[login_id] = {
            "client": client,
            "user_id": str(user_id),
            "phone_number": phone_number,
            "phone_code_hash": sent_code.phone_code_hash,
        }

        return {
            "login_id": login_id,
            "message": "OTP sent to Telegram",
        }

    except Exception:
        await client.disconnect()
        raise


# GET AND VALIDATE PENDING LOGIN

def get_pending_login(login_id, user_id):

    login = pending_logins.get(login_id)

    if not login:
        raise ValueError(
            "Login expired or not found. Please try again."
        )


    if login["user_id"] != str(user_id):
        raise ValueError(
            "You are not authorized to complete this login."
        )

    return login


# VERIFY TELEGRAM OTP

async def verify_telegram_otp(
    login_id: str,
    otp: str,
    user_id,
):

    login = get_pending_login(login_id, user_id)
    client = login["client"]

    try:
        await client.sign_in(
            phone=login["phone_number"],
            code=otp,
            phone_code_hash=login["phone_code_hash"],
        )

    except SessionPasswordNeededError:

        # Keep the client alive because the user must enter 2FA.
        return {
            "requires_2fa": True,
            "message": (
                "Enter your Telegram two-step verification password"
            ),
        }

    except PhoneCodeInvalidError:
        raise ValueError("Invalid OTP. Please try again.")

    except PhoneCodeExpiredError:
        pending_logins.pop(login_id, None)
        await client.disconnect()

        raise ValueError(
            "OTP expired. Please request a new OTP."
        )

    return await save_authenticated_session(
        login_id=login_id,
        user_id=user_id,
    )


# VERIFY TELEGRAM 2FA

async def verify_telegram_2fa(
    login_id: str,
    password: str,
    user_id,
):

    login = get_pending_login(login_id, user_id)
    client = login["client"]

    try:
        await client.sign_in(password=password)

    except PasswordHashInvalidError:
        raise ValueError(
            "Incorrect Telegram 2FA password."
        )

    return await save_authenticated_session(
        login_id=login_id,
        user_id=user_id,
    )


# SAVE AUTHENTICATED TELEGRAM SESSION

async def save_authenticated_session(
    login_id: str,
    user_id,
):

    login = get_pending_login(login_id, user_id)
    client = login["client"]

    try:
        if not await client.is_user_authorized():
            raise ValueError(
                "Telegram authentication failed."
            )

        # Get the authenticated Telegram session.
        session_string = client.session.save()

        # Encrypt before storing in the database.
        encrypted_session = encrypt_session(session_string)

        async with SessionLocal() as db:

            # Check whether this user already has this phone connected.
            connection = await db.scalar(
                select(TelegramConnection).where(
                    TelegramConnection.user_id == user_id,
                    TelegramConnection.phone_number_lookup
                    == create_blind_index(login["phone_number"]),
                )
            )

            if connection:

                # Update existing connection.
                connection.session_encrypted = encrypted_session
                connection.is_active = True

            else:

                # Create a new connection.
                connection = TelegramConnection(
                    user_id=user_id,
                    phone_number=login["phone_number"],
                    phone_number_lookup=create_blind_index(login["phone_number"]),
                    session_encrypted=encrypted_session,
                    is_active=True,
                )

                db.add(connection)

            await db.commit()
            await db.refresh(connection)

            connection_id = str(connection.id)

        return {
            "status": "connected",
            "connection_id": connection_id,
            "phone_number": login["phone_number"],
            "message": "Telegram connected successfully",
        }

    finally:
        # Remove temporary login and close the Telethon client.
        pending_logins.pop(login_id, None)
        await client.disconnect()
