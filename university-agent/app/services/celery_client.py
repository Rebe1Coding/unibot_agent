"""Singleton Celery client for sending tasks to workers."""

from __future__ import annotations

from celery import Celery

from app.config import settings

_celery: Celery | None = None


def get_celery() -> Celery:
    """Return a shared Celery app instance (lazy-initialized)."""
    global _celery
    if _celery is None:
        _celery = Celery(
            "university-agent",
            broker=settings.celery_broker_url,
            backend=settings.celery_result_backend,
        )
    return _celery
