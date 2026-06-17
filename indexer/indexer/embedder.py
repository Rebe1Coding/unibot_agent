"""Embedding wrappers: dense (USER-bge-m3) + sparse BM25 (lazy-loaded singletons).

Hybrid retrieval uses two signals:
- dense semantic vectors from ``deepvk/USER-bge-m3`` (strong on Russian);
- sparse BM25 vectors for exact word matches (surnames, codes, abbreviations),
  which dense embeddings tend to wash out.

USER-bge-m3 needs NO ``query:``/``passage:`` prefixes (unlike e5).
"""

from __future__ import annotations

import logging

from indexer.config import settings

logger = logging.getLogger(__name__)

_model = None
_bm25 = None


def get_model():
    """Lazy-load the dense SentenceTransformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Loaded dense embedding model: %s", settings.embedding_model)
    return _model


def get_bm25():
    """Lazy-load the sparse BM25 model (fastembed)."""
    global _bm25
    if _bm25 is None:
        from fastembed import SparseTextEmbedding

        _bm25 = SparseTextEmbedding(model_name=settings.bm25_model)
        logger.info("Loaded sparse BM25 model: %s", settings.bm25_model)
    return _bm25


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Dense-embed a batch of documents (no prefix — USER-bge-m3)."""
    model = get_model()
    return model.encode(texts, normalize_embeddings=True).tolist()


def embed_documents_sparse(texts: list[str]) -> list[tuple[list[int], list[float]]]:
    """BM25-embed a batch of documents. Returns (indices, values) per text.

    IDF is applied server-side by Qdrant (collection uses Modifier.IDF), so here
    we only emit the document-side term weights.
    """
    bm25 = get_bm25()
    out: list[tuple[list[int], list[float]]] = []
    for emb in bm25.embed(texts):
        out.append((emb.indices.tolist(), emb.values.tolist()))
    return out
