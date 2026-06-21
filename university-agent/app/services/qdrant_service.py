"""Qdrant vector database client for RAG search."""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import QdrantClient, models

from app.config import settings

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None

# Collection names
KNOWLEDGE_BASE = "knowledge_base"
LITERATURE = "literature"

VECTOR_DIM = settings.vector_dim  # Из конфигурации, default=1024 для USER-bge-m3

# Named vectors: dense semantic vector + sparse BM25 vector (hybrid search).
DENSE = "dense"
BM25 = "bm25"


def get_qdrant() -> QdrantClient:
    """Return a shared Qdrant client (lazy-initialized)."""
    global _client
    if _client is None:
        _client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            timeout=30,
        )
    return _client


def close_qdrant() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


# ── Collection management ────────────────────────────────────────────────────


def ensure_collections() -> None:
    """Create collections if they don't exist yet."""
    client = get_qdrant()
    existing = {c.name for c in client.get_collections().collections}

    for name in (KNOWLEDGE_BASE, LITERATURE):
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config={
                    DENSE: models.VectorParams(
                        size=VECTOR_DIM,
                        distance=models.Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    BM25: models.SparseVectorParams(modifier=models.Modifier.IDF),
                },
            )
            logger.info("Created Qdrant collection: %s", name)


# ── Search ───────────────────────────────────────────────────────────────────


def _build_filter(filters: dict[str, Any] | None) -> models.Filter | None:
    if not filters:
        return None
    return models.Filter(
        must=[models.FieldCondition(key=k, match=models.MatchValue(value=v)) for k, v in filters.items()]
    )


def hybrid_search(
    collection: str,
    dense_vector: list[float],
    sparse: tuple[list[int], list[float]],
    limit: int = 10,
    filters: dict[str, Any] | None = None,
) -> list[models.ScoredPoint]:
    """Hybrid search: dense semantic + sparse BM25, fused with Reciprocal Rank Fusion.

    BM25 recovers exact word matches (surnames, codes) that the dense vector
    washes out; the dense vector recovers paraphrases the keywords miss. RRF
    merges both rankings, so no cosine score_threshold applies here.
    """
    client = get_qdrant()
    query_filter = _build_filter(filters)
    sparse_vector = models.SparseVector(indices=sparse[0], values=sparse[1])

    return client.query_points(
        collection_name=collection,
        prefetch=[
            models.Prefetch(
                query=dense_vector,
                using=DENSE,
                limit=limit,
                filter=query_filter,
            ),
            models.Prefetch(
                query=sparse_vector,
                using=BM25,
                limit=limit,
                filter=query_filter,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
    ).points


# ── Health check ─────────────────────────────────────────────────────────────


def ping() -> bool:
    try:
        client = get_qdrant()
        client.get_collections()
        return True
    except Exception:
        logger.exception("Qdrant ping failed")
        return False
