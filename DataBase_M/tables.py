
import uuid

from datetime import datetime, timezone
from security_and_privacy import EncryptedText, create_blind_index

from sqlalchemy import (
    String,
    Text,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    LargeBinary
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column
)


class Base(DeclarativeBase):
    pass


# USER TABLE

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )


# TELEGRAM CONNECTION TABLE

class TelegramConnection(Base):
    __tablename__ = "telegram_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    phone_number: Mapped[str] = mapped_column(
    EncryptedText,
    nullable=False,
    )

    phone_number_lookup: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    session_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )




# TELEGRAM CHAT SYNC TABLE

class TelegramChatSync(Base):
    __tablename__ = "telegram_chat_sync"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_connections.id"),
        nullable=False,
        index=True
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )

    last_message_id: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False
    )

    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "chat_id",
            name="uq_telegram_chat_sync"
        ),
    )


# GMAIL CONNECTION TABLE

class GmailConnection(Base):

    __tablename__ = "gmail_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    email: Mapped[str] = mapped_column(
    EncryptedText,
    nullable=False,
    )

    email_lookup: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    credentials_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "email_lookup",
            name="uq_gmail_user_email_lookup"
        ),
    )


# GMAIL SYNC STATE TABLE

class GmailSyncState(Base):

    __tablename__ = "gmail_sync_state"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gmail_connections.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    history_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )


# TELEGRAM LOGIN CHALLENGE TABLE

class TelegramLoginChallenge(Base):

    __tablename__ = "telegram_login_challenges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    phone_number: Mapped[str] = mapped_column(
    EncryptedText,
    nullable=False,
    )

    phone_code_hash: Mapped[str] = mapped_column(
        EncryptedText,
        nullable=False,
    )

    session_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )


# GMAIL OAUTH STATE TABLE

class GmailOAuthState(Base):

    __tablename__ = "gmail_oauth_states"

    state: Mapped[str] = mapped_column(
        String(128),
        primary_key=True
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # PKCE verifier generated during authorization.
    # It must be reused when exchanging the authorization code.
    code_verifier: Mapped[str | None] = mapped_column(
        EncryptedText,
        nullable=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

class TelegramNotification(Base):
    __tablename__ = "telegram_notification"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    storage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    source: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[str] = mapped_column(String(100), nullable=False)
    chat_name: Mapped[str] = mapped_column(
    EncryptedText,
    nullable=False,
    )
    reminder: Mapped[str] = mapped_column(
        EncryptedText,
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
   
# GMAIL NOTIFICATIONS TABLE

class GmailNotification(Base):
    __tablename__ = "gmail_notifications"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )
    storage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    my_email_id: Mapped[str] = mapped_column(
    EncryptedText,
    nullable=False,
    )

    senders_email_id: Mapped[str] = mapped_column(
        EncryptedText,
        nullable=False,
    )

    text: Mapped[str] = mapped_column(
        EncryptedText,
        nullable=False,
    )

    date: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="not_completed"
    )

    

