
import asyncio
import logging

from fastembed import TextEmbedding

from security_and_privacy import transform_embedding

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384

_embedding_model = None
_embedding_lock = asyncio.Lock()


async def initialize_embedding_model():

    global _embedding_model

    if _embedding_model is not None:
        return

    async with _embedding_lock:

        if _embedding_model is None:

            logger.info(
                "Loading embedding model: %s",
                MODEL_NAME,
            )

            _embedding_model = await asyncio.to_thread(
                TextEmbedding,
                model_name=MODEL_NAME,
            )

            logger.info("Embedding model loaded")


async def generate_document_embedding(
    text: str,
) -> list[float]:

    if not text or not text.strip():
        raise ValueError("Document text cannot be empty")

    if _embedding_model is None:
        await initialize_embedding_model()

    vectors = await asyncio.to_thread(
        lambda: list(_embedding_model.embed([text]))
    )

    original_vector = vectors[0].tolist()

    if len(original_vector) != VECTOR_SIZE:
        raise ValueError(
            f"Expected {VECTOR_SIZE} dimensions, "
            f"received {len(original_vector)}"
        )

    # Apply orthogonal transformation before storing in Qdrant.
    protected_vector = transform_embedding(original_vector)

    return protected_vector


async def generate_query_embedding(
    query: str,
) -> list[float]:

    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")

    if _embedding_model is None:
        await initialize_embedding_model()

    vectors = await asyncio.to_thread(
        lambda: list(
            _embedding_model.query_embed(
                "Represent this sentence for searching relevant passages: "
                + query
            )
        )
    )

    original_vector = vectors[0].tolist()

    if len(original_vector) != VECTOR_SIZE:
        raise ValueError(
            f"Expected {VECTOR_SIZE} dimensions, "
            f"received {len(original_vector)}"
        )

    # Apply exactly the same transformation used for documents.
    protected_vector = transform_embedding(original_vector)

    return protected_vector
