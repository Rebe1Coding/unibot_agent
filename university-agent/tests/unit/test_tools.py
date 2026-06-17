"""Unit tests: agent tools (search, clarification, docx, web)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


class TestAskClarification:
    """ask_clarification tool outputs correct prefix format."""

    def test_output_format(self):
        from app.tools.ask_clarification import CLARIFICATION_PREFIX, ask_clarification

        result = ask_clarification.invoke({"question": "Какой у вас курс?", "options": ["1", "2", "3"]})
        assert result.startswith(CLARIFICATION_PREFIX)
        payload = json.loads(result[len(CLARIFICATION_PREFIX) :])
        assert payload["question"] == "Какой у вас курс?"
        # Три варианта плюс автодобавленный «свой ответ».
        assert len(payload["options"]) == 4
        assert payload["options"][0]["label"] == "1"
        assert payload["options"][-1]["free_text"] is True

    def test_empty_options(self):
        from app.tools.ask_clarification import ask_clarification

        result = ask_clarification.invoke({"question": "Уточните тему", "options": []})
        assert "__CLARIFICATION__" in result


class TestSearchKnowledgeBase:
    """search_knowledge_base tool logic."""

    @pytest.mark.asyncio
    async def test_search_found(self, mock_embedding, mock_qdrant):
        scored = _make_scored(
            score=0.85,
            payload={"text": "Поступление на бюджет", "source": "rules.pdf", "section": "Бакалавриат"},
        )
        mock_qdrant.query_points.return_value = MagicMock(points=[scored])

        from app.tools.search_kb import search_knowledge_base

        result = await search_knowledge_base.ainvoke({"query": "поступление"})
        data = json.loads(result)
        assert data["found"] is True
        assert len(data["chunks"]) == 1
        assert data["chunks"][0]["source"] == "rules.pdf"

    @pytest.mark.asyncio
    async def test_search_not_found(self, mock_embedding, mock_qdrant):
        mock_qdrant.query_points.return_value = MagicMock(points=[])

        from app.tools.search_kb import search_knowledge_base

        result = await search_knowledge_base.ainvoke({"query": "несуществующее"})
        data = json.loads(result)
        assert data["found"] is False
        assert "Релевантных документов не найдено" in data["message"]

    @pytest.mark.asyncio
    async def test_search_failure(self, mock_embedding, mock_qdrant):
        mock_qdrant.query_points.side_effect = RuntimeError("Qdrant crash")

        from app.tools.search_kb import search_knowledge_base

        result = await search_knowledge_base.ainvoke({"query": "тест"})
        data = json.loads(result)
        assert data["found"] is False
        assert "error" in data


class TestSearchLiterature:
    """search_literature tool logic."""

    @pytest.mark.asyncio
    async def test_search_with_filters(self, mock_embedding, mock_qdrant, mocker):
        mocker.patch(
            "app.services.minio_service.presigned_url",
            return_value="http://minio/book.pdf",
        )
        scored = _make_scored(
            score=0.88,
            payload={
                "title": "Линейная алгебра",
                "author": "Иванов",
                "course": 1,
                "subject": "Математика",
                "file_key": "books/algebra.pdf",
            },
        )
        mock_qdrant.query_points.return_value = MagicMock(points=[scored])

        from app.tools.search_literature import search_literature

        result = await search_literature.ainvoke({"query": "алгебра", "course": 1, "subject": "Математика"})
        data = json.loads(result)
        assert data["found"] is True
        assert len(data["books"]) == 1
        assert data["books"][0]["download_url"] == "http://minio/book.pdf"

    @pytest.mark.asyncio
    async def test_book_without_file_key(self, mock_embedding, mock_qdrant):
        scored = _make_scored(
            score=0.7,
            payload={"title": "Учебник без файла"},
        )
        mock_qdrant.query_points.return_value = MagicMock(points=[scored])

        from app.tools.search_literature import search_literature

        result = await search_literature.ainvoke({"query": "учебник"})
        data = json.loads(result)
        assert data["books"][0]["download_url"] is None


class TestThink:
    """think tool — внутреннее размышление перед ответом."""

    def test_returns_acknowledgement(self):
        from app.tools.think import think

        result = think.invoke({"thought": "Студент спрашивает про стипендию, нужно искать в базе."})
        assert isinstance(result, str)
        assert result

    def test_guidelines_in_description(self):
        from app.tools.think import think

        # Спецслучаи (безопасность, сокращения) попадают в описание инструмента,
        # а не в системный промпт.
        assert "ФКТиПМ" in think.description


class TestSearchWeb:
    """search_web tool — external search fallback."""

    @pytest.mark.asyncio
    async def test_no_api_keys_configured(self, monkeypatch):
        # search_web reads the `settings` singleton (frozen at first import),
        # so patch the attributes directly — setenv would not take effect.
        from app.config import settings

        monkeypatch.setattr(settings, "tavily_api_key", "")
        monkeypatch.setattr(settings, "serpapi_api_key", "")

        from app.tools.search_web import search_web

        result = await search_web.ainvoke({"query": "тест"})
        data = json.loads(result)
        assert data["found"] is False
        assert "не настроен API-ключ" in data["message"]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_scored(score: float, payload: dict):
    point = MagicMock()
    point.score = score
    point.payload = payload
    return point
