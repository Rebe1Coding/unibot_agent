"""Conversation memory: per-dialog Redis cache backed by PostgreSQL, trimmed to a token budget."""

from __future__ import annotations

import json
import logging
import uuid

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import delete, func, select

from app.config import settings
from app.models.database import ConversationHistory, Dialog
from app.services import postgres_service, redis_service, token_counter

logger = logging.getLogger(__name__)

_DEFAULT_TITLE = "Новый чат"
_TITLE_MAX = 60


def _to_lc_messages(raw: list[dict]) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for msg in raw:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


async def _redis_messages(user_id: str, dialog_id: str) -> list[dict] | None:
    """Return cached messages, or None if the session key is absent."""
    r = await redis_service.get_redis()
    raw = await r.get(redis_service._session_key(user_id, dialog_id))
    if raw is None:
        return None
    return json.loads(raw).get("messages", [])


async def _pg_messages(user_id: str, dialog_id: str) -> list[dict]:
    """Load a dialog's conversation log from PostgreSQL, oldest first."""
    factory = postgres_service.get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ConversationHistory.role, ConversationHistory.content)
            .where(
                ConversationHistory.user_id == user_id,
                ConversationHistory.dialog_id == dialog_id,
            )
            .order_by(ConversationHistory.created_at)
        )
        return [{"role": role, "content": content} for role, content in result.all()]


async def _cache(user_id: str, dialog_id: str, messages: list[dict]) -> None:
    await redis_service.save_session(
        user_id, dialog_id, {"user_id": user_id, "dialog_id": dialog_id, "messages": messages}
    )


async def load_history(user_id: str, dialog_id: str) -> list[BaseMessage]:
    """Load dialog history (Redis, falling back to PostgreSQL), trimmed to budget."""
    messages = await _redis_messages(user_id, dialog_id)
    source = "redis"
    if messages is None:
        messages = await _pg_messages(user_id, dialog_id)
        await _cache(user_id, dialog_id, messages)
        source = "postgres"

    lc_messages = _to_lc_messages(messages)
    trimmed = token_counter.trim_to_budget(lc_messages, token_counter.history_budget())
    logger.debug("История загружена: dialog=%s source=%s msgs=%d", dialog_id, source, len(trimmed))
    return trimmed


async def save_turn(user_id: str, dialog_id: str, user_message: str, assistant_message: str) -> None:
    """Persist a user+assistant turn, refresh the Redis cache and bump the dialog."""
    factory = postgres_service.get_session_factory()
    async with factory() as session:
        session.add_all(
            [
                ConversationHistory(user_id=user_id, dialog_id=dialog_id, role="user", content=user_message),
                ConversationHistory(user_id=user_id, dialog_id=dialog_id, role="assistant", content=assistant_message),
            ]
        )
        dialog = await session.get(Dialog, dialog_id)
        if dialog is not None:
            dialog.updated_at = func.now()
            if not dialog.title or dialog.title == _DEFAULT_TITLE:
                dialog.title = user_message.strip()[:_TITLE_MAX] or _DEFAULT_TITLE
        await session.commit()

    messages = await _redis_messages(user_id, dialog_id)
    if messages is None:
        messages = await _pg_messages(user_id, dialog_id)
    else:
        messages = messages + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ]
    await _cache(user_id, dialog_id, messages)


# ── Dialog management ────────────────────────────────────────────────────────


async def list_dialogs(user_id: str) -> list[dict]:
    """Return the user's dialogs, most recently updated first."""
    factory = postgres_service.get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Dialog.id, Dialog.title, Dialog.updated_at)
            .where(Dialog.user_id == user_id)
            .order_by(Dialog.updated_at.desc())
        )
        return [
            {"dialog_id": did, "title": title, "updated_at": updated.isoformat()}
            for did, title, updated in result.all()
        ]


async def create_dialog(user_id: str, previous_dialog_id: str | None = None) -> dict:
    """Create a new dialog and archive the previous one's Redis session (1h TTL)."""
    dialog_id = str(uuid.uuid4())
    factory = postgres_service.get_session_factory()
    async with factory() as session:
        session.add(Dialog(id=dialog_id, user_id=user_id, title=_DEFAULT_TITLE))
        await session.commit()

    if previous_dialog_id:
        await redis_service.expire_session(user_id, previous_dialog_id, settings.archive_session_ttl)

    return {"dialog_id": dialog_id, "title": _DEFAULT_TITLE}


async def get_or_create_active_dialog(user_id: str) -> str:
    """Return the most recent dialog id, creating one if the user has none."""
    dialogs = await list_dialogs(user_id)
    if dialogs:
        return dialogs[0]["dialog_id"]
    created = await create_dialog(user_id)
    return created["dialog_id"]


async def dialog_messages(user_id: str, dialog_id: str) -> list[dict]:
    """Full message log of a dialog (for switching in the UI)."""
    messages = await _redis_messages(user_id, dialog_id)
    if messages is None:
        messages = await _pg_messages(user_id, dialog_id)
        await _cache(user_id, dialog_id, messages)
    return messages


async def delete_dialog(user_id: str, dialog_id: str) -> None:
    """Remove a dialog and its messages from PostgreSQL and Redis."""
    await redis_service.clear_session(user_id, dialog_id)
    factory = postgres_service.get_session_factory()
    async with factory() as session:
        await session.execute(
            delete(ConversationHistory).where(
                ConversationHistory.user_id == user_id,
                ConversationHistory.dialog_id == dialog_id,
            )
        )
        await session.execute(delete(Dialog).where(Dialog.id == dialog_id, Dialog.user_id == user_id))
        await session.commit()
