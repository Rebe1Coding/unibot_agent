"""Unit tests: Pydantic request/response schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestChatRequest:
    """ChatRequest model validation."""

    def test_valid_minimal(self):
        from app.models.schemas import ChatRequest

        req = ChatRequest(user_id="user_001", dialog_id="dlg_001", message="Привет!")
        assert req.user_id == "user_001"
        assert req.message == "Привет!"
        assert req.clarification_response is None

    def test_valid_with_clarification(self):
        from app.models.schemas import ChatRequest

        req = ChatRequest(
            user_id="user99",
            dialog_id="dlg99",
            message="расписание",
            clarification_response="1 курс",
        )
        assert req.clarification_response == "1 курс"

    def test_user_id_too_short(self):
        from app.models.schemas import ChatRequest

        with pytest.raises(ValidationError, match="at least 1 character"):
            ChatRequest(user_id="", message="test")

    def test_user_id_too_long(self):
        from app.models.schemas import ChatRequest

        with pytest.raises(ValidationError, match="at most 64 characters"):
            ChatRequest(user_id="x" * 65, message="test")

    def test_user_id_invalid_characters(self):
        from app.models.schemas import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(user_id="user@name!", message="test")
        with pytest.raises(ValidationError):
            ChatRequest(user_id="user name", message="test")

    def test_message_too_long(self):
        from app.models.schemas import ChatRequest

        with pytest.raises(ValidationError, match="at most 4096 characters"):
            ChatRequest(user_id="u1", message="x" * 4097)

    def test_message_empty(self):
        from app.models.schemas import ChatRequest

        with pytest.raises(ValidationError, match="at least 1 character"):
            ChatRequest(user_id="u1", message="")


class TestChatResponse:
    """ChatResponse model construction."""

    def test_minimal_response(self):
        from app.models.schemas import ChatResponse

        resp = ChatResponse(answer="Всё хорошо!")
        assert resp.answer == "Всё хорошо!"
        assert resp.sources == []
        assert resp.files == []
        assert resp.clarification is None

    def test_response_with_sources(self):
        from app.models.schemas import ChatResponse, Source

        resp = ChatResponse(
            answer="Ответ",
            sources=[Source(title="FAQ", url="http://example.com", snippet="Текст...")],
            files=["http://minio/file.docx"],
        )
        assert len(resp.sources) == 1
        assert resp.sources[0].title == "FAQ"
        assert resp.files == ["http://minio/file.docx"]

    def test_response_with_clarification(self):
        from app.models.schemas import ChatResponse, Clarification, ClarificationOption

        resp = ChatResponse(
            answer="Уточните курс",
            clarification=Clarification(
                question="Какой у вас курс?",
                options=[ClarificationOption(label="1", value="1"), ClarificationOption(label="2", value="2")],
            ),
        )
        assert resp.clarification.question == "Какой у вас курс?"
        assert len(resp.clarification.options) == 2


class TestVoiceResponse:
    """VoiceResponse model."""

    def test_default_status(self):
        from app.models.schemas import VoiceResponse

        resp = VoiceResponse(task_id="abc123")
        assert resp.status == "processing"


class TestHistoryResponse:
    """History response models."""

    def test_empty_history(self):
        from app.models.schemas import HistoryResponse

        resp = HistoryResponse(user_id="u1", messages=[])
        assert resp.user_id == "u1"
        assert resp.messages == []

    def test_history_with_messages(self):
        from app.models.schemas import HistoryMessage, HistoryResponse

        resp = HistoryResponse(
            user_id="u1",
            messages=[HistoryMessage(role="user", content="Привет")],
        )
        assert len(resp.messages) == 1
        assert resp.messages[0].role == "user"


class TestHealthSchemas:
    """Health check models."""

    def test_service_health(self):
        from app.models.schemas import ServiceHealth

        sh = ServiceHealth(status="ok", latency_ms=1.5)
        assert sh.status == "ok"
        assert sh.latency_ms == 1.5

    def test_health_response(self):
        from app.models.schemas import HealthResponse, ServiceHealth

        hr = HealthResponse(
            status="ok",
            services={
                "redis": ServiceHealth(status="ok", latency_ms=0.5),
                "postgres": ServiceHealth(status="ok", latency_ms=1.2),
            },
        )
        assert hr.status == "ok"
        assert len(hr.services) == 2
