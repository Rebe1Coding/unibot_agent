"""Unit tests: MCP tool loader (mcp_loader.py)."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings


@pytest.fixture
def mcp_servers(monkeypatch):
    """Configure a single fake MCP server in settings."""
    cfg = {"weather": {"transport": "streamable_http", "url": "http://mcp:8080/mcp"}}
    monkeypatch.setattr(settings, "mcp_servers", cfg)
    return cfg


@pytest.fixture
def fake_mcp_client(monkeypatch):
    """Patch MultiServerMCPClient and return its (class_mock, instance_mock)."""
    instance = MagicMock()
    instance.get_tools = AsyncMock(return_value=[])
    client_cls = MagicMock(return_value=instance)

    import langchain_mcp_adapters.client as client_mod

    monkeypatch.setattr(client_mod, "MultiServerMCPClient", client_cls)
    return client_cls, instance


class TestLoadMcpTools:
    """Connecting to MCP servers and merging their tools."""

    @pytest.mark.asyncio
    async def test_no_servers_configured_returns_empty(self, monkeypatch):
        monkeypatch.setattr(settings, "mcp_servers", {})

        from app.agent.mcp_loader import load_mcp_tools_list

        assert await load_mcp_tools_list() == []

    @pytest.mark.asyncio
    async def test_loads_tools_from_servers(self, mcp_servers, fake_mcp_client):
        client_cls, instance = fake_mcp_client
        fake_tools = [MagicMock(), MagicMock()]
        instance.get_tools.return_value = fake_tools

        from app.agent.mcp_loader import load_mcp_tools_list

        tools = await load_mcp_tools_list()

        assert tools == fake_tools
        client_cls.assert_called_once_with(mcp_servers)
        instance.get_tools.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connection_failure_returns_empty(self, mcp_servers, fake_mcp_client):
        _client_cls, instance = fake_mcp_client
        instance.get_tools = AsyncMock(side_effect=ConnectionError("server unreachable"))

        from app.agent.mcp_loader import load_mcp_tools_list

        assert await load_mcp_tools_list() == []

    @pytest.mark.asyncio
    async def test_client_construction_failure_returns_empty(self, mcp_servers, monkeypatch):
        import langchain_mcp_adapters.client as client_mod

        monkeypatch.setattr(
            client_mod,
            "MultiServerMCPClient",
            MagicMock(side_effect=ValueError("bad config")),
        )

        from app.agent.mcp_loader import load_mcp_tools_list

        assert await load_mcp_tools_list() == []

    @pytest.mark.asyncio
    async def test_missing_package_returns_empty(self, mcp_servers, monkeypatch):
        # A None entry in sys.modules makes `from langchain_mcp_adapters.client import ...` raise ImportError.
        monkeypatch.setitem(sys.modules, "langchain_mcp_adapters.client", None)

        from app.agent.mcp_loader import load_mcp_tools_list

        assert await load_mcp_tools_list() == []
