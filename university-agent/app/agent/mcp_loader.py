"""Load LangChain tools from configured MCP servers."""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def load_mcp_tools_list() -> list:
    """Connect to the configured MCP servers and return their tools (empty on failure)."""
    servers = settings.mcp_servers
    if not servers:
        logger.info("MCP: серверы не сконфигурированы, пропускаю")
        return []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning("langchain-mcp-adapters не установлен, MCP-инструменты недоступны")
        return []

    try:
        client = MultiServerMCPClient(servers)
        tools = await client.get_tools()
        logger.info("MCP: загружено инструментов %d из серверов %s", len(tools), list(servers))
        return tools
    except Exception:
        logger.warning("MCP: не удалось загрузить инструменты", exc_info=True)
        return []
