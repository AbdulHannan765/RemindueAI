import uvicorn
import asyncio
import uuid
import jwt
import logging

from pathlib import Path
from typing import Literal

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from DataBase_M.database import SessionLocal

from DataBase_M.tables import (
    User,
    GmailConnection,
    TelegramConnection,
    TelegramNotification,
    GmailNotification,
)

from DataBase_M.auth import (
    hash_password,
    verify_password,
    create_access_token,
    ALGORITHM,
)
from RAG.rag_service import ask_remindue

from DataBase_M.config import SECRET_KEY

from Gmail_connector.gmail_auth import (
    create_gmail_authorization_url,
    complete_gmail_oauth,
)

from Gmail_connector.gmail_service import sync_gmail

from Telegram_connector.telegram_auth import (
    start_telegram_login,
    verify_telegram_otp,
    verify_telegram_2fa,
)

from Telegram_connector.telegram_service import sync_telegram
from contextlib import asynccontextmanager

from RAG.embeddings import initialize_embedding_model
from vector_database.qdrant_db import (
    initialize_qdrant,
    qdrant_client,
)
from RAG.notification_ingestion import (
    update_qdrant_notification_status,
)

@asynccontextmanager
async def lifespan(app: FastAPI):

    await initialize_embedding_model()

    await initialize_qdrant()

    yield

    await qdrant_client.close()



# LOGGING

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# APPLICATION SETUP

app = FastAPI(title="Remindue API",lifespan=lifespan,)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)

# auto_error=False allows us to return our own 401 response
bearer_scheme = HTTPBearer(auto_error=False)


# DATABASE DEPENDENCY

async def get_db():
    async with SessionLocal() as db:
        yield db


# REQUEST SCHEMAS
class RAGAskRequest(BaseModel):

    question: str = Field(
        min_length=2,
        max_length=2000,
    )

    top_k: int = Field(
        default=6,
        ge=1,
        le=10,
    )

    source: Literal[
        "telegram",
        "gmail",
    ] | None = None

    category: str | None = Field(
        default=None,
        max_length=100,
    )
class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class TelegramStartRequest(BaseModel):
    phone_number: str = Field(min_length=5, max_length=30)


class TelegramOTPRequest(BaseModel):
    login_id: str
    otp: str = Field(min_length=4, max_length=10)


class Telegram2FARequest(BaseModel):
    login_id: str
    password: str = Field(min_length=1, max_length=256)


class SyncRequest(BaseModel):
    # Messages per chat for the initial Telegram sync
    telegram_messages: int | None = Field(default=None, ge=1, le=1000)
    # Past days of emails for the initial Gmail sync
    email_days: int | None = Field(default=None, ge=1, le=365)


class StatusUpdateRequest(BaseModel):
    status: Literal["completed", "not_completed"]


# SIGNUP

@app.post("/api/auth/signup")
async def signup(
    data: SignupRequest,
    db: AsyncSession = Depends(get_db),
):

    username = data.username.strip()

    if not username:
        raise HTTPException(
            status_code=400,
            detail="Username cannot be empty",
        )

    existing_user = await db.scalar(
        select(User).where(User.username == username)
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Username already exists",
        )

    user = User(
        username=username,
        password_hash=hash_password(data.password),
    )

    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)

    except IntegrityError:
        await db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Username already exists",
        )

    return {
        "message": "Registration successful",
        "user_id": str(user.id),
        "username": user.username,
    }


# LOGIN

@app.post("/api/auth/login")
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(
        select(User).where(
            User.username == data.username.strip()
        )
    )

    user = result.scalar_one_or_none()

    if not user or not verify_password(
        data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    token = create_access_token(str(user.id))

    return {
        "message": "Login successful",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "username": user.username,
        },
    }


# AUTHENTICATED USER

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: AsyncSession = Depends(get_db),
):

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise ValueError("Missing token subject")

        user_uuid = uuid.UUID(user_id)

    except (
        jwt.InvalidTokenError,
        ValueError,
        TypeError,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    user = await db.get(User, user_uuid)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    return user


# GET CURRENT USER

@app.get("/api/auth/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):

    return {
        "user_id": str(current_user.id),
        "username": current_user.username,
    }


# GMAIL - START OAUTH

@app.post("/api/gmail/connect")
async def gmail_connect(
    current_user: User = Depends(get_current_user),
):

    try:
        authorization_url = await create_gmail_authorization_url(
            current_user.id
        )

        return {
            "authorization_url": authorization_url
        }

    except Exception:
        logger.exception("Failed to start Gmail OAuth")

        raise HTTPException(
            status_code=500,
            detail="Could not start Gmail connection",
        )


# GMAIL - OAUTH CALLBACK

@app.get("/api/gmail/callback")
async def gmail_callback(request: Request):

    error = request.query_params.get("error")

    if error:
        return RedirectResponse(
            url="/connectors?gmail=error",
            status_code=303,
        )

    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        return RedirectResponse(
            url="/connectors?gmail=error",
            status_code=303,
        )

    try:
        result = await complete_gmail_oauth(
            code=code,
            state=state,
        )

        logger.info(
            "Gmail connected for connection %s",
            result["connection_id"],
        )

        return RedirectResponse(
            url="/connectors?gmail=connected",
            status_code=303,
        )

    except ValueError:
        logger.warning("Gmail OAuth state validation failed")

        return RedirectResponse(
            url="/connectors?gmail=error",
            status_code=303,
        )

    except Exception:
        logger.exception("Gmail OAuth callback failed")

        return RedirectResponse(
            url="/connectors?gmail=error",
            status_code=303,
        )


# TELEGRAM - START LOGIN

@app.post("/api/telegram/start")
async def telegram_start(
    payload: TelegramStartRequest,
    current_user: User = Depends(get_current_user),
):

    try:
        result = await start_telegram_login(
            user_id=current_user.id,
            phone_number=payload.phone_number.strip(),
        )

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception:
        logger.exception("Telegram login initialization failed")

        raise HTTPException(
            status_code=502,
            detail="Could not start Telegram login",
        )


# TELEGRAM - VERIFY OTP

@app.post("/api/telegram/verify-otp")
async def telegram_verify_otp(
    payload: TelegramOTPRequest,
    current_user: User = Depends(get_current_user),
):

    try:
        result = await verify_telegram_otp(
            login_id=payload.login_id,
            otp=payload.otp,
            user_id=current_user.id,
        )

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception:
        logger.exception("Telegram OTP verification failed")

        raise HTTPException(
            status_code=502,
            detail="Telegram OTP verification failed",
        )


# TELEGRAM - VERIFY 2FA

@app.post("/api/telegram/verify-2fa")
async def telegram_verify_2fa(
    payload: Telegram2FARequest,
    current_user: User = Depends(get_current_user),
):

    try:
        result = await verify_telegram_2fa(
            login_id=payload.login_id,
            password=payload.password,
            user_id=current_user.id,
        )

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception:
        logger.exception("Telegram 2FA verification failed")

        raise HTTPException(
            status_code=502,
            detail="Telegram 2FA verification failed",
        )
# DASHBOARD PAGE

@app.get("/dashboard")
async def dashboard():

    return FileResponse(
        STATIC_DIR / "dashboard.html"
    )

# CONNECTOR STATUS

@app.get("/api/connectors/status")
async def connector_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    gmail_connection = await db.scalar(
        select(GmailConnection)
        .where(
            GmailConnection.user_id == current_user.id,
            GmailConnection.is_active.is_(True),
        )
        .order_by(
            GmailConnection.created_at.desc()
        )
        .limit(1)
    )

    telegram_connection = await db.scalar(
        select(TelegramConnection)
        .where(
            TelegramConnection.user_id == current_user.id,
            TelegramConnection.is_active.is_(True),
        )
        .order_by(
            TelegramConnection.created_at.desc()
        )
        .limit(1)
    )

    return {
        "gmail": {
            "connected": gmail_connection is not None,
            "email": (
                gmail_connection.email
                if gmail_connection else None
            ),
        },

        "telegram": {
            "connected": telegram_connection is not None,
            "phone_number": (
                telegram_connection.phone_number
                if telegram_connection else None
            ),
        },
    }


# SYNC JOBS (in-memory, one per user)

# Suitable for a single backend process, same as pending_logins.
sync_jobs: dict[str, dict] = {}


# Keep references to background tasks so they are not garbage collected
background_tasks: set = set()


async def count_notifications(user_id):

    async with SessionLocal() as db:

        telegram_count = await db.scalar(
            select(func.count())
            .select_from(TelegramNotification)
            .where(TelegramNotification.user_id == user_id)
        )

        gmail_count = await db.scalar(
            select(func.count())
            .select_from(GmailNotification)
            .where(GmailNotification.user_id == user_id)
        )

    return (telegram_count or 0) + (gmail_count or 0)


async def run_sync_job(user_id, telegram_messages, email_days):

    key = str(user_id)
    errors = []
    details = []

    try:

        before = await count_notifications(user_id)

        # ---------- Telegram ----------
        if telegram_messages:

            async with SessionLocal() as db:
                result = await db.execute(
                    select(TelegramConnection.id).where(
                        TelegramConnection.user_id == user_id,
                        TelegramConnection.is_active.is_(True),
                    )
                )
                telegram_ids = [row[0] for row in result.all()]

            if not telegram_ids:
                errors.append(
                    "Telegram: no connected account. "
                    "Connect Telegram on the Connectors page."
                )

            for connection_id in telegram_ids:

                sync_jobs[key]["message"] = "Syncing Telegram..."

                try:
                    summary = await sync_telegram(
                        user_id=user_id,
                        connection_id=connection_id,
                        INITIAL_MESSAGES_PER_CHAT=telegram_messages,
                        overlap_size=2,
                        chunk_size=10,
                        noti_batch_size=4,
                    )

                    details.append(
                        f"Telegram: {summary['total_chats_found']} chats, "
                        f"{summary['new_messages_fetched']} messages fetched, "
                        f"{summary['notifications_saved']} reminders saved"
                    )

                except Exception as error:
                    logger.exception("Telegram sync failed")
                    errors.append(f"Telegram: {error}")

        # ---------- Gmail ----------
        if email_days:

            async with SessionLocal() as db:
                result = await db.execute(
                    select(GmailConnection.id).where(
                        GmailConnection.user_id == user_id,
                        GmailConnection.is_active.is_(True),
                    )
                )
                gmail_ids = [row[0] for row in result.all()]

            if not gmail_ids:
                errors.append(
                    "Gmail: no connected account. "
                    "Connect Gmail on the Connectors page."
                )

            for connection_id in gmail_ids:

                sync_jobs[key]["message"] = "Syncing Gmail..."

                try:
                    summary = await sync_gmail(
                        user_id=user_id,
                        connection_id=connection_id,
                        initial_query=f"newer_than:{email_days}d",
                        batch_size=10,
                        max_concurrent_batches=2,
                        max_retries=5,
                        include_spam_trash=False,
                        max_results=500,
                        wait_seconds=12,
                    )

                    details.append(
                        f"Gmail ({summary['sync_type']}): "
                        f"{summary['total_ids_found']} emails found, "
                        f"{summary['new_messages_fetched']} fetched"
                    )

                except Exception as error:
                    logger.exception("Gmail sync failed")
                    errors.append(f"Gmail: {error}")

        after = await count_notifications(user_id)
        details.append(f"{after - before} new notifications")

    except Exception as error:
        logger.exception("Sync job failed")
        errors.append(str(error))

    finally:
        sync_jobs[key] = {
            "running": False,
            "message": " | ".join(details) or "Sync finished",
            "errors": errors,
        }


# SYNC - START

@app.post("/api/sync")
async def start_sync(
    payload: SyncRequest,
    current_user: User = Depends(get_current_user),
):

    if not payload.telegram_messages and not payload.email_days:
        raise HTTPException(
            status_code=400,
            detail="Nothing to sync",
        )

    key = str(current_user.id)

    if sync_jobs.get(key, {}).get("running"):
        raise HTTPException(
            status_code=409,
            detail="A sync is already running",
        )

    sync_jobs[key] = {
        "running": True,
        "message": "Starting sync...",
        "errors": [],
    }

    task = asyncio.create_task(
        run_sync_job(
            current_user.id,
            payload.telegram_messages,
            payload.email_days,
        )
    )

    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)

    return {"status": "started"}


# SYNC - STATUS

@app.get("/api/sync/status")
async def sync_status(
    current_user: User = Depends(get_current_user),
):

    return sync_jobs.get(
        str(current_user.id),
        {"running": False, "message": "", "errors": []},
    )
# RAG - ASK REMINDUE

@app.post("/api/rag/ask")
async def rag_ask(
    payload: RAGAskRequest,
    current_user: User = Depends(get_current_user),
):

    try:

        result = await ask_remindue(
            user_id=str(current_user.id),

            question=payload.question.strip(),

            top_k=payload.top_k,

            source=payload.source,

            category=payload.category,
        )

        return {
            "success": True,
            **result,
        }

    except Exception:

        logger.exception(
            "RAG request failed for user %s",
            current_user.id,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not generate your answer",
        )


# NOTIFICATIONS - LIST

@app.get("/api/notifications")
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    telegram_rows = (
        await db.scalars(
            select(TelegramNotification)
            .where(TelegramNotification.user_id == current_user.id)
            .order_by(TelegramNotification.id.desc())
        )
    ).all()

    gmail_rows = (
        await db.scalars(
            select(GmailNotification)
            .where(GmailNotification.user_id == current_user.id)
            .order_by(GmailNotification.id.desc())
        )
    ).all()

    items = []

    for n in telegram_rows:
        items.append({
            "key": f"telegram-{n.id}",
            "text": n.reminder,
            "source": "telegram",
            "category": n.category,
            "status": n.status,
            "date": n.date,
            "origin": n.chat_name,
        })

    for n in gmail_rows:
        items.append({
            "key": f"gmail-{n.id}",
            "text": n.text,
            "source": "gmail",
            "category": n.category,
            "status": n.status,
            "date": n.date,
            "origin": n.senders_email_id,
        })

    return {"notifications": items}


# NOTIFICATIONS - CHANGE STATUS


@app.patch("/api/notifications/{key}/status")
async def update_notification_status(
    key: str,
    payload: StatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    # 1. Extract source and notification ID
    try:
        source, raw_id = key.split("-", 1)
        notification_id = int(raw_id)

    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid notification key",
        )

    # 2. Identify the notification table
    model = {
        "telegram": TelegramNotification,
        "gmail": GmailNotification,
    }.get(source)

    if model is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid notification source",
        )

    # 3. Find the notification belonging to the logged-in user
    notification = await db.scalar(
        select(model).where(
            model.id == notification_id,
            model.user_id == current_user.id,
        )
    )

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found",
        )

    # 4. Update PostgreSQL
    notification.status = payload.status

    # Capture storage_id before committing
    storage_id = notification.storage_id

    try:
        await db.commit()

    except Exception:
        await db.rollback()

        logger.exception(
            "PostgreSQL status update failed for %s",
            key,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not update notification status",
        )

    # 5. Update Qdrant
    try:
        await update_qdrant_notification_status(
            storage_id=storage_id,
            status=payload.status,
        )

    except Exception:
        logger.exception(
            "PostgreSQL status updated, but Qdrant update failed "
            "for notification %s",
            key,
        )

    # 6. Return response
    return {
        "success": True,
        "key": key,
        "status": payload.status,
    }
# CONNECTORS PAGE

@app.get("/connectors")
async def connectors():

    return FileResponse(
        STATIC_DIR / "connectors.html"
    )


# FRONTEND - LOGIN / SIGNUP PAGE

@app.get("/")
async def home():

    return FileResponse(
        STATIC_DIR / "login_signup.html"
    )

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8000))
    reload_flag = os.getenv("ENVIRONMENT", "").lower() != "production"
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=reload_flag)