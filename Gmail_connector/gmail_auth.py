
import json
import secrets

from datetime import datetime, timedelta, timezone

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

from starlette.concurrency import run_in_threadpool

from sqlalchemy import select

from security_and_privacy import create_blind_index

from DataBase_M.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GMAIL_REDIRECT_URI,
    GMAIL_SCOPES,
    encrypt_session,
    decrypt_session,
)

from DataBase_M.database import SessionLocal

from DataBase_M.tables import (
    GmailConnection,
    GmailSyncState,
    GmailOAuthState,
)


# GENERAL HELPERS

def utc_now():
    return datetime.now(timezone.utc)


# GOOGLE OAUTH FLOW

def create_google_flow(state=None, code_verifier=None):

    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GMAIL_REDIRECT_URI],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=GMAIL_SCOPES,
        state=state,
        code_verifier=code_verifier,
        autogenerate_code_verifier=False,
    )

    flow.redirect_uri = GMAIL_REDIRECT_URI

    return flow

# STEP 1: GENERATE GOOGLE AUTHORIZATION URL

async def create_gmail_authorization_url(user_id):

    state = secrets.token_urlsafe(48)

    # Generate PKCE verifier explicitly.
    # token_urlsafe(64) produces a valid verifier.
    code_verifier = secrets.token_urlsafe(64)

    flow = create_google_flow(
        state=state,
        code_verifier=code_verifier,
    )

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        code_challenge_method="S256",
    )

    if not flow.code_verifier:
        raise RuntimeError(
            "Google OAuth PKCE verifier was not generated"
        )

    async with SessionLocal() as db:

        oauth_state = GmailOAuthState(
            state=state,
            user_id=user_id,
            code_verifier=code_verifier,
            expires_at=utc_now() + timedelta(minutes=10),
        )

        db.add(oauth_state)

        await db.commit()

    return authorization_url

# STEP 2: VALIDATE AND CONSUME OAUTH STATE

async def consume_oauth_state(state):

    async with SessionLocal() as db:

        result = await db.execute(
            select(GmailOAuthState)
            .where(
                GmailOAuthState.state == state,
                GmailOAuthState.expires_at > utc_now(),
            )
            .with_for_update()
        )

        oauth_state = result.scalar_one_or_none()

        if not oauth_state:
            raise ValueError(
                "Invalid or expired Gmail OAuth state. "
                "Please reconnect Gmail."
            )

        user_id = oauth_state.user_id
        code_verifier = oauth_state.code_verifier

        if not code_verifier:
            raise ValueError(
                "Missing Gmail OAuth PKCE verifier. "
                "Please reconnect Gmail."
            )

    
        await db.delete(oauth_state)

        await db.commit()

        return user_id, code_verifier


# GOOGLE API HELPER

def fetch_gmail_profile(credentials):

    service = build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )

    return service.users().getProfile(
        userId="me"
    ).execute()


# STEP 3: COMPLETE GOOGLE OAUTH

async def complete_gmail_oauth(code, state):

    # Retrieve the original user and PKCE verifier.
    user_id, code_verifier = await consume_oauth_state(state)

    flow = create_google_flow(
        state=state,
        code_verifier=code_verifier,
    )

    # Exchange authorization code using the original PKCE verifier.
    await run_in_threadpool(
        flow.fetch_token,
        code=code,
    )

    credentials = flow.credentials

    # Fetch connected Gmail account information.
    profile = await run_in_threadpool(
        fetch_gmail_profile,
        credentials,
    )

    email = profile["emailAddress"]

    email_lookup = create_blind_index(email)

    # Encrypt credentials before database storage.
    encrypted_credentials = encrypt_session(
        credentials.to_json()
    )

    async with SessionLocal() as db:

        result = await db.execute(
            select(GmailConnection).where(
                GmailConnection.user_id == user_id,
                GmailConnection.email_lookup == email_lookup,
            )
        )

        connection = result.scalar_one_or_none()

        if connection:

            connection.credentials_encrypted = encrypted_credentials
            connection.is_active = True

        else:

            connection = GmailConnection(
                user_id=user_id,
                email=email,
                email_lookup=email_lookup,
                credentials_encrypted=encrypted_credentials,
                is_active=True,
            )

            db.add(connection)

        await db.flush()

        result = await db.execute(
            select(GmailSyncState).where(
                GmailSyncState.connection_id == connection.id
            )
        )

        sync_state = result.scalar_one_or_none()

        if not sync_state:

            sync_state = GmailSyncState(
                connection_id=connection.id,
                history_id=None,
                last_synced_at=None,
            )

            db.add(sync_state)

        await db.commit()

        await db.refresh(connection)

        return {
            "connection_id": str(connection.id),
            "email": email,
            "status": "connected",
        }
# STEP 4: GET AND REFRESH USER GMAIL CREDENTIALS

async def get_gmail_credentials(user_id, connection_id):

    async with SessionLocal() as db:

        result = await db.execute(
            select(GmailConnection).where(
                GmailConnection.id == connection_id,
                GmailConnection.user_id == user_id,
                GmailConnection.is_active.is_(True),
            )
        )

        connection = result.scalar_one_or_none()

        if not connection:
            raise ValueError("Gmail connection not found")

        encrypted = connection.credentials_encrypted

    # Decrypt the user's credentials.
    credentials_data = json.loads(
        decrypt_session(encrypted)
    )

    credentials = Credentials.from_authorized_user_info(
        credentials_data,
        scopes=GMAIL_SCOPES,
    )

    # Refresh expired access tokens automatically.
    if credentials.expired:

        if not credentials.refresh_token:
            raise ValueError(
                "Gmail authorization expired. "
                "Please reconnect Gmail."
            )

        try:

            await run_in_threadpool(
                credentials.refresh,
                Request(),
            )

        except RefreshError as exc:

            raise ValueError(
                "Gmail authorization is no longer valid. "
                "Please reconnect Gmail."
            ) from exc

        # Encrypt refreshed credentials.
        refreshed_encrypted = encrypt_session(
            credentials.to_json()
        )

        # Save refreshed credentials in PostgreSQL.
        async with SessionLocal() as db:

            result = await db.execute(
                select(GmailConnection).where(
                    GmailConnection.id == connection_id,
                    GmailConnection.user_id == user_id,
                    GmailConnection.is_active.is_(True),
                )
            )

            connection = result.scalar_one_or_none()

            if not connection:
                raise ValueError("Gmail connection not found")

            connection.credentials_encrypted = refreshed_encrypted

            await db.commit()

    return credentials
