"""Middleware that generates and propagates X-Request-ID."""

from __future__ import annotations

import contextvars
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable для доступа из любого места в async-стеке
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Берём из заголовка (пробрасывается из Telegram-бота/Nginx) или генерируем
        rid = request.headers.get("X-Request-ID", uuid.uuid4().hex[:8])
        request_id_var.set(rid)

        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
