"""Tool: search_web — external web search fallback via Tavily or SerpAPI."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from app.config import settings

logger = logging.getLogger(__name__)


@tool
async def search_web(query: str) -> str:
    """Поиск информации в интернете.

    Используй этот инструмент ТОЛЬКО когда:
    - в базе знаний университета нет ответа на вопрос
    - студент спрашивает о внешних ресурсах или общих темах
    - нужна актуальная информация, которой нет в локальных источниках

    Args:
        query: Поисковый запрос.

    Returns:
        JSON с результатами поиска.
    """
    # Try Tavily first, then SerpAPI
    if settings.tavily_api_key:
        return await _search_tavily(query)
    if settings.serpapi_api_key:
        return await _search_serpapi(query)

    return json.dumps(
        {"found": False, "message": "Веб-поиск недоступен: не настроен API-ключ."},
        ensure_ascii=False,
    )


async def _search_tavily(query: str) -> str:
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "max_results": 5,
                    "search_depth": "basic",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in data.get("results", []):
            results.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:500],
                }
            )

        return json.dumps({"found": bool(results), "results": results}, ensure_ascii=False)

    except Exception as e:
        logger.exception("Tavily search failed")
        return json.dumps({"found": False, "error": str(e)}, ensure_ascii=False)


async def _search_serpapi(query: str) -> str:
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://serpapi.com/search",
                params={
                    "api_key": settings.serpapi_api_key,
                    "q": query,
                    "num": 5,
                    "hl": "ru",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in data.get("organic_results", []):
            results.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "snippet": r.get("snippet", "")[:500],
                }
            )

        return json.dumps({"found": bool(results), "results": results}, ensure_ascii=False)

    except Exception as e:
        logger.exception("SerpAPI search failed")
        return json.dumps({"found": False, "error": str(e)}, ensure_ascii=False)
