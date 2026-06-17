"""Embedding model wrapper for vectorizing text."""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from app.config import settings

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="embed")

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()
_bm25 = None
_bm25_lock = threading.Lock()


def get_model():
    """Lazy-load the dense SentenceTransformer model (thread-safe)."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Loaded embedding model: %s", settings.embedding_model)
        return _model


def get_bm25():
    """Lazy-load the sparse BM25 model (fastembed, thread-safe)."""
    global _bm25
    if _bm25 is not None:
        return _bm25
    with _bm25_lock:
        if _bm25 is not None:
            return _bm25
        from fastembed import SparseTextEmbedding

        _bm25 = SparseTextEmbedding(model_name=settings.bm25_model)
        logger.info("Loaded sparse BM25 model: %s", settings.bm25_model)
        return _bm25


def embed_query(text: str) -> list[float]:
    """Dense-embed a query (no prefix — USER-bge-m3)."""
    model = get_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_query_sparse(text: str) -> tuple[list[int], list[float]]:
    """BM25-embed a query. Returns (indices, values) for a sparse vector."""
    bm25 = get_bm25()
    emb = next(iter(bm25.query_embed([text])))
    return emb.indices.tolist(), emb.values.tolist()


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Dense-embed a batch of documents (no prefix — USER-bge-m3)."""
    model = get_model()
    return model.encode(texts, normalize_embeddings=True).tolist()


async def embed_query_async(text: str) -> list[float]:
    """Async wrapper — runs dense embedding in thread pool to avoid blocking the loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, embed_query, text)


async def embed_query_sparse_async(text: str) -> tuple[list[int], list[float]]:
    """Async wrapper for sparse BM25 query embedding."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, embed_query_sparse, text)


async def embed_documents_async(texts: list[str]) -> list[list[float]]:
    """Async wrapper for batch document embedding."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, embed_documents, texts)


def shutdown_executor() -> None:
    """Gracefully shutdown the embedding thread pool."""
    _executor.shutdown(wait=False)
    logger.info("Embedding executor shut down")
