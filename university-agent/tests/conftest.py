"""Shared test fixtures and configuration."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch):
    """Isolate app settings to test values for each test."""
    os.environ.setdefault("INTERNAL_API_KEY", "test-api-key-12345")
    os.environ.setdefault("AUTH_DISABLED", "true")
    os.environ.setdefault("ROUTERAI_API_KEY", "sk-test-placeholder")
    os.environ.setdefault("ROUTERAI_MODEL", "openai/gpt-4o")
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("QDRANT_HOST", "localhost")
    os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
    os.environ.setdefault("EMBEDDING_MODEL", "deepvk/USER-bge-m3")
    os.environ.setdefault("VECTOR_DIM", "1024")

    # The `settings` singleton is frozen at first import of app.config, which can
    # happen before this fixture runs (e.g. a module-level import in another test).
    # Pin auth on the singleton so test order can't enable it mid-suite; reverted automatically.
    from app.config import settings

    monkeypatch.setattr(settings, "auth_disabled", True)
    monkeypatch.setattr(settings, "internal_api_key", "")
    yield


@pytest.fixture
def app():
    """Return the FastAPI application instance."""
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client(app) -> TestClient:
    """Return a synchronous TestClient for the app."""
    return TestClient(app)


class _FakeRedis:
    """Fake Redis client for tests.

    We use MagicMock as the base so fixtures can set .return_value on methods.
    The ``pipeline`` method returns a _FakePipeline to support ``async with``.
    """

    def __init__(self, mock):
        self._mock = mock
        self.pipeline = MagicMock(return_value=_FakePipeline(self))

    # Delegate all attribute access to the underlying MagicMock
    def __getattr__(self, name):
        if name == "_mock" or name == "pipeline":
            raise AttributeError(name)
        return getattr(self._mock, name)


class _FakePipeline:
    """Sync fake for aioredis Pipeline supporting async context manager protocol."""

    def __init__(self, redis_mock):
        self._redis = redis_mock
        self.set_called = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def watch(self, key):
        pass

    async def get(self, key):
        return self._redis.get.return_value

    def multi(self):
        pass

    def set(self, key, value, ex=None):
        self.set_called = True

    async def execute(self):
        pass


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis client for service-level tests.

    Returns a _FakeRedis that delegates to an inner MagicMock but exposes
    pipeline() as a sync _FakePipeline for ``async with`` support.
    """
    mock = mocker.patch("app.services.redis_service.get_redis")
    inner_mock = MagicMock()
    inner_mock.ping = AsyncMock(return_value=True)
    inner_mock.get = AsyncMock(return_value=None)
    inner_mock.set = AsyncMock()
    inner_mock.delete = AsyncMock()
    inner_mock.aclose = AsyncMock()

    redis_instance = _FakeRedis(inner_mock)
    mock.return_value = redis_instance
    return inner_mock


@pytest.fixture
def mock_qdrant(mocker):
    """Mock Qdrant client for service-level tests."""
    mock = mocker.patch("app.services.qdrant_service.get_qdrant")
    qdrant_instance = MagicMock()
    qdrant_instance.get_collections.return_value = MagicMock(collections=[])
    qdrant_instance.query_points.return_value = MagicMock(points=[])
    mock.return_value = qdrant_instance
    return qdrant_instance


@pytest.fixture
def mock_minio(mocker):
    """Mock MinIO client for service-level tests."""
    mock = mocker.patch("app.services.minio_service.get_minio")
    minio_instance = MagicMock()
    minio_instance.list_buckets.return_value = []
    minio_instance.bucket_exists.return_value = True
    mock.return_value = minio_instance
    return minio_instance


@pytest.fixture
def mock_postgres_engine(mocker):
    """Mock PostgreSQL engine for service-level tests.

    Returns the patch mock for get_engine so tests can control
    return_value / side_effect.
    """
    mock_engine = mocker.patch("app.services.postgres_service.get_engine")
    engine = MagicMock()

    class _FakeAsyncConnection:
        """Supports ``async with engine.connect() as conn: ...``"""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, stmt):
            pass

        async def commit(self):
            pass

    def _fake_connect():
        return _FakeAsyncConnection()

    engine.connect = _fake_connect
    mock_engine.return_value = engine
    return mock_engine


@pytest.fixture
def mock_embedding(mocker):
    """Mock embedding service to avoid loading the heavy model."""
    return mocker.patch(
        "app.services.embedding_service.embed_query_async",
        new_callable=AsyncMock,
        return_value=[0.1] * 1024,
    )
