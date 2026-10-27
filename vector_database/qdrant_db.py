import os
import logging

from dotenv import load_dotenv

from qdrant_client import AsyncQdrantClient, models

load_dotenv()

logger = logging.getLogger(__name__)

QDRANT_URL = os.environ["QDRANT_URL"]
QDRANT_API_KEY = os.environ["QDRANT_API_KEY"]

QDRANT_COLLECTION = os.getenv(
    "QDRANT_COLLECTION",
    "remindue_notifications",
)

VECTOR_SIZE = 384

qdrant_client = AsyncQdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    timeout=30,
)


async def initialize_qdrant():

    collections = await qdrant_client.get_collections()

    exists = any(
        collection.name == QDRANT_COLLECTION
        for collection in collections.collections
    )

    if not exists:

        await qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )

        logger.info("Created Qdrant collection")

    # Create indexes for fields used in filters.
    for field_name, field_schema in [
        ("user_id", models.PayloadSchemaType.KEYWORD),
        ("source", models.PayloadSchemaType.KEYWORD),
        ("category", models.PayloadSchemaType.KEYWORD),
        ("status", models.PayloadSchemaType.KEYWORD),
    ]:

        await qdrant_client.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name=field_name,
            field_schema=field_schema,
        )

    logger.info("Qdrant initialized successfully")