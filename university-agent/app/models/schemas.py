"""Pydantic schemas for API request/response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ── Chat ─────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    dialog_id: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    message: str = Field(..., min_length=1, max_length=4096)
    clarification_response: str | None = Field(None, max_length=1024)


class NewDialogRequest(BaseModel):
    previous_dialog_id: str | None = Field(None, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class DialogInfo(BaseModel):
    dialog_id: str
    title: str
    updated_at: str | None = None


class DialogListResponse(BaseModel):
    user_id: str
    dialogs: list[DialogInfo]


class Source(BaseModel):
    title: str
    url: str | None = None
    snippet: str | None = None


class ClarificationOption(BaseModel):
    label: str
    value: str
    free_text: bool = False  # вариант «свой ответ» — интерфейс показывает поле ввода


class Clarification(BaseModel):
    question: str
    options: list[ClarificationOption]


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    clarification: Clarification | None = None


# ── Voice ────────────────────────────────────────────────────────────────────


class VoiceResponse(BaseModel):
    task_id: str
    status: str = "processing"


class VoiceStatusResponse(BaseModel):
    status: str
    text: str | None = None
    download_url: str | None = None
    error: str | None = None


# ── History ──────────────────────────────────────────────────────────────────


class HistoryMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime | None = None


class HistoryResponse(BaseModel):
    user_id: str
    messages: list[HistoryMessage]


# ── Health ───────────────────────────────────────────────────────────────────


class ServiceHealth(BaseModel):
    status: str
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    status: str
    services: dict[str, ServiceHealth]
