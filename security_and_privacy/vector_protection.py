
import os
import hashlib
import logging
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)

VECTOR_SIZE = 384


def _get_seed():

    secret = os.getenv("QDRANT_ROTATION_SECRET")

    if not secret:
        raise RuntimeError(
            "QDRANT_ROTATION_SECRET is missing from environment variables"
        )

    digest = hashlib.sha256(
        secret.encode("utf-8")
    ).digest()

    return int.from_bytes(digest[:8], byteorder="big")


@lru_cache(maxsize=4)
def get_rotation_matrix(dimension: int):

    if dimension != VECTOR_SIZE:
        raise ValueError(
            f"Expected {VECTOR_SIZE} dimensions, got {dimension}"
        )

    rng = np.random.default_rng(_get_seed())

    random_matrix = rng.standard_normal(
        (dimension, dimension)
    )

    q, r = np.linalg.qr(random_matrix)

    # Make the QR decomposition deterministic for this seed.
    signs = np.sign(np.diag(r))
    signs[signs == 0] = 1

    q = q * signs[np.newaxis, :]

    return q.astype(np.float32)


def transform_embedding(embedding: list[float]) -> list[float]:

    vector = np.asarray(
        embedding,
        dtype=np.float32
    )

    if vector.ndim != 1:
        raise ValueError(
            "Embedding must be a one-dimensional vector"
        )

    if len(vector) != VECTOR_SIZE:
        raise ValueError(
            f"Expected {VECTOR_SIZE} dimensions, got {len(vector)}"
        )

    if not np.all(np.isfinite(vector)):
        raise ValueError(
            "Embedding contains NaN or infinite values"
        )

    rotation_matrix = get_rotation_matrix(len(vector))

    transformed = rotation_matrix @ vector

    return transformed.tolist()
