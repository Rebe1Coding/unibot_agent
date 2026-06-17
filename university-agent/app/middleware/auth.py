"""API key authentication middleware."""

from __future__ import annotations

import hmac
import logging

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)

# Эндпоинты, не требующие аутентификации
_PUBLIC_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # Явный dev-режим вместо "пусто = без auth"
        if settings.auth_disabled:
            logger.warning("Auth disabled (AUTH_DISABLED=true) — dev mode only!")
            return await call_next(request)

        if not settings.internal_api_key:
            raise HTTPException(
                status_code=500,
                detail="INTERNAL_API_KEY not configured. Set AUTH_DISABLED=true for dev mode.",
            )

        api_key = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(api_key, settings.internal_api_key):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

        return await call_next(request)
