"""Integration tests: service singletons, health checks, and initialization."""

from __future__ import annotations

import pytest


class TestRedisService:
    """Redis service — singleton pattern and health."""

    @pytest.mark.asyncio
    async def test_get_redis_returns_same_instance(self, mock_redis):
        from app.services.redis_service import get_redis

        r1 = await get_redis()
        r2 = await get_redis()
        assert r1 is r2

    @pytest.mark.asyncio
    async def test_ping_success(self, mock_redis):
        from app.services.redis_service import ping

        ok = await ping()
        assert ok is True

    @pytest.mark.asyncio
    async def test_ping_failure(self, mock_redis):
        mock_redis.ping.side_effect = RuntimeError("connection lost")

        from app.services.redis_service import ping

        ok = await ping()
        assert ok is False

    @pytest.mark.asyncio
    async def test_load_session_empty(self, mock_redis):
        mock_redis.get.return_value = None

        from app.services.redis_service import load_session

        session = await load_session("user1")
        assert session["user_id"] == "user1"
        assert session["messages"] == []

    @pytest.mark.asyncio
    async def test_save_and_clear_session(self, mock_redis):
        from app.services.redis_service import clear_session, save_session

        await save_session("user1", {"user_id": "user1", "messages": []})
        assert mock_redis.set.called

        await clear_session("user1")
        assert mock_redis.delete.called


class TestQdrantService:
    """Qdrant service — collections and search."""

    def test_get_qdrant_singleton(self, mock_qdrant):
        from app.services.qdrant_service import get_qdrant

        c1 = get_qdrant()
        c2 = get_qdrant()
        assert c1 is c2

    def test_ping_success(self, mock_qdrant):
        from app.services.qdrant_service import ping

        ok = ping()
        assert ok is True

    def test_ping_failure(self, mock_qdrant):
        mock_qdrant.get_collections.side_effect = RuntimeError("Qdrant down")

        from app.services.qdrant_service import ping

        ok = ping()
        assert ok is False

    def test_collection_names_defined(self):
        from app.services.qdrant_service import KNOWLEDGE_BASE, LITERATURE

        assert KNOWLEDGE_BASE == "knowledge_base"
        assert LITERATURE == "literature"


class TestMinioService:
    """MinIO service — bucket and upload/download."""

    def test_get_minio_singleton(self, mock_minio):
        from app.services.minio_service import get_minio

        m1 = get_minio()
        m2 = get_minio()
        assert m1 is m2

    def test_ping_success(self, mock_minio):
        from app.services.minio_service import ping

        ok = ping()
        assert ok is True

    def test_ping_failure(self, mock_minio):
        mock_minio.list_buckets.side_effect = RuntimeError("MinIO down")

        from app.services.minio_service import ping

        ok = ping()
        assert ok is False


class TestPostgresService:
    """PostgreSQL service — engine and connections."""

    def test_get_engine_singleton(self, mock_postgres_engine):
        from app.services.postgres_service import get_engine

        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2

    @pytest.mark.asyncio
    async def test_ping_success(self, mock_postgres_engine):
        # conftest sets up a working engine via mock_postgres_engine fixture
        from app.services.postgres_service import ping

        ok = await ping()
        assert ok is True

    @pytest.mark.asyncio
    async def test_ping_failure(self, mock_postgres_engine):
        # mock_postgres_engine is now the patch mock for get_engine()
        mock_postgres_engine.side_effect = RuntimeError("DB crash")

        from app.services.postgres_service import ping

        ok = await ping()
        assert ok is False


class TestEmbeddingService:
    """Embedding service — model loading and encoding."""

    @pytest.mark.asyncio
    async def test_embed_query_async_returns_correct_dimensions(self, mock_embedding):
        from app.services.embedding_service import embed_query_async

        vec = await embed_query_async("тест")
        assert len(vec) == 1024
        assert isinstance(vec[0], float)


class TestCeleryClient:
    """Celery client singleton."""

    def test_get_celery_singleton(self):
        from app.services.celery_client import get_celery

        c1 = get_celery()
        c2 = get_celery()
        assert c1 is c2
