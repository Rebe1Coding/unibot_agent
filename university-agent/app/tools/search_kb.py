"""Tool: search_knowledge_base — RAG search over university documents in Qdrant."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from app.services import embedding_service, qdrant_service

logger = logging.getLogger(__name__)


@tool
async def search_knowledge_base(query: str) -> str:
    """Поиск по базе знаний университета: правила поступления, учебные планы, стипендии, FAQ и другие документы.

    Используй этот инструмент, когда студент спрашивает о:
    - правилах поступления и проходных баллах
    - учебных программах и расписании
    - стипендиях, общежитиях, студенческой жизни
    - внутренних правилах и регламентах вуза

    Args:
        query: Поисковый запрос на естественном языке.

    Returns:
        JSON со списком релевантных фрагментов документов и их источников.
    """
    try:
        dense_vector = await embedding_service.embed_query_async(query)
        sparse_vector = await embedding_service.embed_query_sparse_async(query)
        results = qdrant_service.hybrid_search(
            collection=qdrant_service.KNOWLEDGE_BASE,
            dense_vector=dense_vector,
            sparse=sparse_vector,
            limit=10,
        )

        if not results:
            return json.dumps(
                {"found": False, "message": "Релевантных документов не найдено."},
                ensure_ascii=False,
            )

        chunks = []
        for point in results:
            payload = point.payload or {}
            chunks.append(
                {
                    "text": payload.get("text", ""),
                    "source": payload.get("source", "неизвестный источник"),
                    "section": payload.get("section", ""),
                    "score": round(point.score, 3),
                }
            )

        return json.dumps(
            {"found": True, "chunks": chunks},
            ensure_ascii=False,
        )

    except Exception as e:
        logger.exception("search_knowledge_base failed")
        return json.dumps(
            {"found": False, "error": f"Ошибка поиска: {e}"},
            ensure_ascii=False,
        )
