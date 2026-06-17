"""Qdrant client wrapper (lazy-loaded singleton)."""

from __future__ import annotations

import contextlib
import logging
import uuid

from qdrant_client import QdrantClient, models

from indexer.config import settings

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None

KNOWLEDGE_BASE = "knowledge_base"
LITERATURE = "literature"
VECTOR_DIM = 1024  # deepvk/USER-bge-m3, distance: COSINE

# Named vectors: a dense semantic vector and a sparse BM25 vector (hybrid search).
DENSE = "dense"
BM25 = "bm25"

ALLOWED_COLLECTIONS = {KNOWLEDGE_BASE, LITERATURE}


def _dense_config() -> dict:
    return {
        DENSE: models.VectorParams(
            size=VECTOR_DIM,
            distance=models.Distance.COSINE,
        ),
    }


def _sparse_config() -> dict:
    # Modifier.IDF makes Qdrant apply the BM25 inverse-document-frequency term
    # at query time, so the indexer only needs to emit document term weights.
    return {
        BM25: models.SparseVectorParams(modifier=models.Modifier.IDF),
    }


def get_client() -> QdrantClient:
    """Return a shared Qdrant client (lazy-initialized)."""
    global _client
    if _client is None:
        _client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            timeout=30,
        )
    return _client


def collection_exists(collection: str) -> bool:
    client = get_client()
    try:
        existing = {c.name for c in client.get_collections().collections}
        return collection in existing
    except Exception:
        return False


def _ensure_collection(collection: str) -> None:
    """Create collection if it doesn't exist."""
    if not collection_exists(collection):
        client = get_client()
        client.create_collection(
            collection_name=collection,
            vectors_config=_dense_config(),
            sparse_vectors_config=_sparse_config(),
        )
        logger.info("Created Qdrant collection: %s", collection)


def get_stats() -> dict:
    """Return points_count and status for each collection."""
    client = get_client()
    result = {}
    for name in (KNOWLEDGE_BASE, LITERATURE):
        try:
            info = client.get_collection(name)
            result[name] = {
                "points_count": info.points_count,
                "status": "ok",
            }
        except Exception:
            result[name] = {
                "points_count": 0,
                "status": "not_created",
            }
    return result


def make_point_id(collection: str, source: str, chunk_index: int) -> str:
    """Deterministic UUID for a chunk."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{collection}:{source}:{chunk_index}"))


def upsert_batch(
    collection: str,
    ids: list[str],
    vectors: list[list[float]],
    payloads: list[dict],
    sparse_vectors: list[tuple[list[int], list[float]]] | None = None,
) -> None:
    """Upsert a batch of points (dense + optional sparse BM25) into the collection."""
    _ensure_collection(collection)
    client = get_client()

    points = []
    for i, point_id in enumerate(ids):
        vector: dict = {DENSE: vectors[i]}
        if sparse_vectors is not None:
            indices, values = sparse_vectors[i]
            vector[BM25] = models.SparseVector(indices=indices, values=values)
        points.append(
            models.PointStruct(
                id=point_id,
                vector=vector,
                payload=payloads[i],
            )
        )

    client.upsert(collection_name=collection, points=points)


def clear_collection(collection: str) -> None:
    """Delete and recreate a collection."""
    client = get_client()
    with contextlib.suppress(Exception):
        client.delete_collection(collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=_dense_config(),
        sparse_vectors_config=_sparse_config(),
    )
    logger.info("Cleared and recreated collection: %s", collection)


def scroll_sample(collection: str, limit: int = 10) -> list[dict]:
    """Return a sample of points from the collection."""
    if not collection_exists(collection):
        return []
    client = get_client()
    points, _ = client.scroll(
        collection_name=collection,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    result = []
    for point in points:
        payload = point.payload or {}
        text_preview = ""
        if "text" in payload:
            text_preview = payload["text"][:200]
        result.append(
            {
                "id": str(point.id),
                "payload": payload,
                "text_preview": text_preview,
            }
        )
    return result
