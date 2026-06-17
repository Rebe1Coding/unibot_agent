"""Async PostgreSQL client via SQLAlchemy."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.models.database import Base

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=5,
            echo=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Yield an async session (use as async context manager or dependency)."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db() -> None:
    """Create tables from metadata and apply lightweight column migrations."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all не меняет существующие таблицы — добавляем dialog_id вручную
        await conn.execute(
            text("ALTER TABLE conversation_history ADD COLUMN IF NOT EXISTS dialog_id VARCHAR(36)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_conversation_history_dialog_id "
                 "ON conversation_history (dialog_id)")
        )
    logger.info("Database tables ensured via create_all() + migrations")


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


# ── Health check ─────────────────────────────────────────────────────────────


async def ping() -> bool:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("PostgreSQL ping failed")
        return False
