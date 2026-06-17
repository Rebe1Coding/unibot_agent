from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def fake_containers():
    return [
        SimpleNamespace(
            short_id="abc123",
            name="university-agent",
            status="running",
            labels={
                "com.docker.compose.project": "unibot",
                "com.docker.compose.service": "university-agent",
            },
            image=SimpleNamespace(tags=["unibot-university-agent:latest"], short_id="img1"),
        ),
        SimpleNamespace(
            short_id="def456",
            name="postgres",
            status="running",
            labels={
                "com.docker.compose.project": "unibot",
                "com.docker.compose.service": "postgres",
            },
            image=SimpleNamespace(tags=["postgres:16-alpine"], short_id="img2"),
        ),
    ]


@pytest.fixture
def mock_docker(monkeypatch, fake_containers):
    from app import docker_client as dc

    fake_client = MagicMock()
    fake_client.ping.return_value = True
    fake_client.containers.list.return_value = fake_containers

    monkeypatch.setattr(dc, "_client", fake_client)
    monkeypatch.setattr(dc, "get_client", lambda: fake_client)
    yield fake_client
    monkeypatch.setattr(dc, "_client", None)


@pytest.fixture
async def client(mock_docker):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        async with app.router.lifespan_context(app):
            yield ac
