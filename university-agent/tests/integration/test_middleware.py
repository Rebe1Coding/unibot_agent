"""Integration tests: API key middleware and request ID middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.middleware.auth import _PUBLIC_PATHS, APIKeyMiddleware


class TestPublicPaths:
    """Verify the set of public paths."""

    def test_health_is_public(self):
        assert "/health" in _PUBLIC_PATHS

    def test_metrics_is_public(self):
        assert "/metrics" in _PUBLIC_PATHS

    def test_api_chat_is_not_public(self):
        assert "/api/chat" not in _PUBLIC_PATHS


class TestAPIKeyMiddlewareUnit:
    """Unit-level tests of the APIKeyMiddleware.dispatch() logic.

    We call dispatch() directly to avoid Starlette's BaseHTTPMiddleware
    async task group behavior that swallows HTTPException differently
    across versions.
    """

    @pytest.fixture
    def middleware(self):
        return APIKeyMiddleware(MagicMock())

    @pytest.mark.asyncio
    async def test_public_path_passes(self, middleware, mocker):
        from app.config import settings

        mocker.patch.object(settings, "auth_disabled", False)
        mocker.patch.object(settings, "internal_api_key", "")

        request = MagicMock()
        request.url.path = "/health"
        call_next = AsyncMock()

        result = await middleware.dispatch(request, call_next)
        assert result is call_next.return_value

    @pytest.mark.asyncio
    async def test_auth_disabled_passes(self, middleware, mocker):
        from app.config import settings

        mocker.patch.object(settings, "auth_disabled", True)
        mocker.patch.object(settings, "internal_api_key", "")

        request = MagicMock()
        request.url.path = "/api/chat"
        call_next = AsyncMock()

        result = await middleware.dispatch(request, call_next)
        assert result is call_next.return_value

    @pytest.mark.asyncio
    async def test_no_key_configured_raises_500(self, middleware, mocker):
        from app.config import settings

        mocker.patch.object(settings, "auth_disabled", False)
        mocker.patch.object(settings, "internal_api_key", "")

        request = MagicMock()
        request.url.path = "/api/chat"
        call_next = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, call_next)
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_missing_key_raises_401(self, middleware, mocker):
        from app.config import settings

        mocker.patch.object(settings, "auth_disabled", False)
        mocker.patch.object(settings, "internal_api_key", "secret")

        request = MagicMock()
        request.headers = {}
        request.url.path = "/api/chat"
        call_next = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, call_next)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_key_raises_401(self, middleware, mocker):
        from app.config import settings

        mocker.patch.object(settings, "auth_disabled", False)
        mocker.patch.object(settings, "internal_api_key", "secret")

        request = MagicMock()
        request.headers = {"X-API-Key": "wrong"}
        request.url.path = "/api/chat"
        call_next = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, call_next)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_key_passes(self, middleware, mocker):
        from app.config import settings

        mocker.patch.object(settings, "auth_disabled", False)
        mocker.patch.object(settings, "internal_api_key", "secret")

        request = MagicMock()
        request.headers = {"X-API-Key": "secret"}
        request.url.path = "/api/chat"
        call_next = AsyncMock()

        result = await middleware.dispatch(request, call_next)
        assert result is call_next.return_value


class TestRequestIDMiddlewareIntegration:
    """Request ID generation and propagation via TestClient (real app)."""

    def test_generates_request_id_if_not_provided(self, client):
        resp = client.get("/health")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) == 8

    def test_propagates_provided_request_id(self, client):
        resp = client.get("/health", headers={"X-Request-ID": "custom-rid"})
        assert resp.headers["X-Request-ID"] == "custom-rid"
