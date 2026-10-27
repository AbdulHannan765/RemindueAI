import logging
import uuid

from qdrant_client import models

from RAG.embeddings import generate_document_embedding

from vector_database.qdrant_db import (
    qdrant_client,
    QDRANT_COLLECTION,
)

from security_and_privacy import (
    encrypt_payload,
)

logger = logging.getLogger(__name__)


async def index_notification(
    *,
    storage_id,
    user_id,
    reminder_text,
    source,
    date,
    category,
    status,
    chat_name=None,
    origin=None,
):

    if not reminder_text or not reminder_text.strip():
        raise ValueError("Reminder text cannot be empty")

    # Embedding generation remains unchanged.
    # Your generate_document_embedding() already applies
    # Random Orthogonal Transformation.
    embedding = await generate_document_embedding(
        reminder_text
    )

    # Encrypt sensitive payload fields.
    encrypted_reminder_text = encrypt_payload(
        reminder_text
    )

    encrypted_chat_name = encrypt_payload(
        chat_name
    )

    encrypted_origin = encrypt_payload(
        origin or chat_name
    )

    payload = {
        "notification_id": str(storage_id),
        "user_id": str(user_id),

        # Encrypted fields
        "reminder_text": encrypted_reminder_text,
        "chat_name": encrypted_chat_name,
        "origin": encrypted_origin,

        # Non-sensitive metadata
        "source": source.lower(),
        "date": date,
        "category": category.upper() if category else None,
        "status": status or "not_completed",
    }

    await qdrant_client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[
            models.PointStruct(
                id=str(storage_id),
                vector=embedding,
                payload=payload,
            )
        ],
        wait=True,
    )

    logger.info(
        "Indexed notification %s for user %s",
        storage_id,
        user_id,
    )


def make_storage_id(
    user_id,
    source,
    date,
    origin,
    reminder_text,
):
    identity = "|".join([
        str(user_id),
        source.lower(),
        str(date),
        str(origin or ""),
        reminder_text.strip(),
    ])

    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        identity,
    )


async def update_qdrant_notification_status(
    storage_id,
    status,
):

    await qdrant_client.set_payload(
        collection_name=QDRANT_COLLECTION,
        payload={
            "status": status,
        },
        points=[
            str(storage_id),
        ],
        wait=True,
    )