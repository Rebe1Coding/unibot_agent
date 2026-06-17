"""Tool: search_literature — search textbooks and study materials in Qdrant + MinIO."""

from __future__ import annotations

import contextlib
import json
import logging

from langchain_core.tools import tool

from app.services import embedding_service, minio_service, qdrant_service

logger = logging.getLogger(__name__)


@tool
async def search_literature(query: str, course: int | None = None, subject: str | None = None) -> str:
    """Поиск учебной литературы: книги, учебники, методические пособия.

    Используй этот инструмент, когда студент просит:
    - «посоветуй книгу по...»
    - «где почитать про...»
    - «учебник по линейной алгебре»
    - «литература для 2 курса»

    Args:
        query: Описание того, что ищет студент.
        course: Номер курса (1–4), если указан.
        subject: Название предмета, если указано.

    Returns:
        JSON со списком найденных книг и ссылками на скачивание.
    """
    try:
        dense_vector = await embedding_service.embed_query_async(query)
        sparse_vector = await embedding_service.embed_query_sparse_async(query)

        filters: dict = {}
        if course is not None:
            filters["course"] = course
        if subject is not None:
            filters["subject"] = subject

        results = qdrant_service.hybrid_search(
            collection=qdrant_service.LITERATURE,
            dense_vector=dense_vector,
            sparse=sparse_vector,
            limit=10,
            filters=filters if filters else None,
        )

        if not results:
            return json.dumps(
                {"found": False, "message": "Подходящая литература не найдена."},
                ensure_ascii=False,
            )

        books = []
        for point in results:
            payload = point.payload or {}
            object_name = payload.get("file_key")
            download_url = None
            if object_name:
                with contextlib.suppress(Exception):
                    download_url = minio_service.presigned_url(object_name)

            books.append(
                {
                    "title": payload.get("title", "Без названия"),
                    "author": payload.get("author", ""),
                    "course": payload.get("course"),
                    "subject": payload.get("subject", ""),
                    "download_url": download_url,
                    "score": round(point.score, 3),
                }
            )

        return json.dumps({"found": True, "books": books}, ensure_ascii=False)

    except Exception as e:
        logger.exception("search_literature failed")
        return json.dumps(
            {"found": False, "error": f"Ошибка поиска литературы: {e}"},
            ensure_ascii=False,
        )
