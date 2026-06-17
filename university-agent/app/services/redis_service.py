"""Async Redis client for session memory and semantic caching."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return a shared async Redis connection (lazy-initialized)."""
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


# ── Session memory ───────────────────────────────────────────────────────────


def _session_key(user_id: str, dialog_id: str) -> str:
    return f"session:{user_id}:{dialog_id}"


async def load_session(user_id: str, dialog_id: str) -> dict[str, Any]:
    """Load a dialog session from Redis. Returns empty structure if absent."""
    r = await get_redis()
    raw = await r.get(_session_key(user_id, dialog_id))
    if raw is None:
        return {"user_id": user_id, "dialog_id": dialog_id, "messages": []}
    return json.loads(raw)


async def save_session(user_id: str, dialog_id: str, session: dict[str, Any]) -> None:
    """Persist a dialog session with the default TTL."""
    r = await get_redis()
    await r.set(
        _session_key(user_id, dialog_id),
        json.dumps(session, ensure_ascii=False),
        ex=settings.memory_ttl,
    )


async def expire_session(user_id: str, dialog_id: str, ttl: int) -> None:
    """Mark a dialog session for expiry without deleting it immediately."""
    r = await get_redis()
    await r.expire(_session_key(user_id, dialog_id), ttl)


async def clear_session(user_id: str, dialog_id: str) -> None:
    r = await get_redis()
    await r.delete(_session_key(user_id, dialog_id))


# ── Health check ─────────────────────────────────────────────────────────────


async def ping() -> bool:
    try:
        r = await get_redis()
        return await r.ping()
    except Exception:
        logger.exception("Redis ping failed")
        return False
