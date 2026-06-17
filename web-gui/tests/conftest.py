import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


@pytest.fixture
def configure_api_key(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-key")
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        async with app.router.lifespan_context(app):
            yield ac


@pytest.fixture
def mock_upstream():
    with respx.mock(base_url=settings.api_base_url, assert_all_called=False) as mock:
        yield mock
