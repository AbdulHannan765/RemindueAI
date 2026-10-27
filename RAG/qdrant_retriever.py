
import logging

from qdrant_client import models

from vector_database.qdrant_db import (
    qdrant_client,
    QDRANT_COLLECTION,
)

from security_and_privacy import (
    decrypt_payload,
)

from RAG.embeddings import generate_query_embedding

logger = logging.getLogger(__name__)


async def retrieve_notifications(
    user_id: str,
    query: str,
    top_k: int = 6,
    source: str | None = None,
    category: str | None = None,
):

    if not user_id:
        raise ValueError("user_id is required")

    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")

    top_k = min(max(int(top_k), 1), 10)

  
    query_vector = await generate_query_embedding(
        query.strip()
    )

    # Always filter by authenticated user.
    conditions = [
        models.FieldCondition(
            key="user_id",
            match=models.MatchValue(
                value=str(user_id),
            ),
        )
    ]

    if source:
        conditions.append(
            models.FieldCondition(
                key="source",
                match=models.MatchValue(
                    value=source.lower(),
                ),
            )
        )

    if category:
        conditions.append(
            models.FieldCondition(
                key="category",
                match=models.MatchValue(
                    value=category.upper(),
                ),
            )
        )

    # Semantic search in Qdrant.
    response = await qdrant_client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        query_filter=models.Filter(
            must=conditions,
        ),
        limit=top_k,
        with_payload=True,
        with_vectors=False,
    )

    results = []

    for point in response.points:

        payload = point.payload or {}

        encrypted_reminder_text = payload.get(
            "reminder_text"
        )

        if not encrypted_reminder_text:
            continue

        try:
            # Decrypt sensitive payload fields.
            reminder_text = decrypt_payload(
                encrypted_reminder_text
            )

            chat_name = decrypt_payload(
                payload.get("chat_name")
            )

            origin = decrypt_payload(
                payload.get("origin")
            )

        except ValueError:
            logger.exception(
                "Could not decrypt notification %s",
                payload.get("notification_id"),
            )
            continue

        if not reminder_text:
            continue

        results.append({

            "notification_id": payload.get(
                "notification_id"
            ),

            "text": reminder_text,

            "source": payload.get("source"),

            "date": payload.get("date"),

            "chat_name": chat_name,

            "origin": origin,

            "category": payload.get("category"),

            "status": payload.get("status"),

            "score": float(point.score),

        })

    logger.info(
        "Retrieved %s notifications for user %s",
        len(results),
        user_id,
    )

    return results
