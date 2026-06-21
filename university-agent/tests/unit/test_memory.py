"""Unit tests: conversation memory (memory.py)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.models.database import ConversationHistory


class _FakeSession:
    """Async-context-manager stand-in for a SQLAlchemy AsyncSession."""

    def __init__(self, rows: list | None = None):
        self._rows = rows or []
        self.added: list = []
        self.executed: list = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def add_all(self, objs):
        self.added.extend(objs)

    async def get(self, model, pk):
        return None

    async def execute(self, stmt):
        self.executed.append(stmt)
        result = MagicMock()
        result.all.return_value = self._rows
        return result

    async def commit(self):
        self.committed = True


@pytest.fixture
def fake_pg(mocker):
    """Patch the PostgreSQL session factory to yield in-memory fake sessions."""
    factory = MagicMock()
    factory.rows = []
    factory.sessions = []

    def make_session():
        session = _FakeSession(factory.rows)
        factory.sessions.append(session)
        return session

    factory.side_effect = make_session
    mocker.patch("app.services.postgres_service.get_session_factory", return_value=factory)
    return factory


class TestLoadHistory:
    """Loading conversation history into LangChain messages."""

    @pytest.mark.asyncio
    async def test_redis_miss_falls_back_to_pg(self, mock_redis, fake_pg):
        mock_redis.get.return_value = None  # no cache → PostgreSQL

        from app.agent.memory import load_history

        history = await load_history("user1", "dlg1")
        assert history == []
        mock_redis.set.assert_awaited()  # PG result cached back to Redis

    @pytest.mark.asyncio
    async def test_redis_hit_messages(self, mock_redis):
        session = {
            "user_id": "user1",
            "messages": [
                {"role": "user", "content": "Привет"},
                {"role": "assistant", "content": "Здравствуйте!"},
            ],
        }
        mock_redis.get.return_value = json.dumps(session, ensure_ascii=False)

        from app.agent.memory import load_history

        history = await load_history("user1", "dlg1")
        assert len(history) == 2
        assert history[0].type == "human"
        assert history[0].content == "Привет"
        assert history[1].type == "ai"
        assert history[1].content == "Здравствуйте!"

    @pytest.mark.asyncio
    async def test_unknown_role_skipped(self, mock_redis):
        session = {
            "user_id": "user1",
            "messages": [
                {"role": "unknown", "content": "что-то"},
                {"role": "user", "content": "Вопрос"},
            ],
        }
        mock_redis.get.return_value = json.dumps(session, ensure_ascii=False)

        from app.agent.memory import load_history

        history = await load_history("user1", "dlg1")
        assert len(history) == 1
        assert history[0].content == "Вопрос"


class TestSaveTurn:
    """Persisting a turn to PostgreSQL and refreshing the Redis cache."""

    @pytest.mark.asyncio
    async def test_save_appends_and_caches(self, mock_redis, fake_pg):
        existing = json.dumps(
            {"user_id": "user1", "messages": [{"role": "user", "content": "Старое"}]},
            ensure_ascii=False,
        )
        mock_redis.get.return_value = existing

        from app.agent.memory import save_turn

        await save_turn("user1", "dlg1", "Новое", "Ответ")

        inserted = fake_pg.sessions[0].added
        assert len(inserted) == 2
        assert all(isinstance(row, ConversationHistory) for row in inserted)
        assert [row.role for row in inserted] == ["user", "assistant"]
        mock_redis.set.assert_awaited()


class TestDeleteDialog:
    """Deleting a dialog from the Redis cache and PostgreSQL."""

    @pytest.mark.asyncio
    async def test_delete_clears_redis_and_pg(self, mock_redis, fake_pg):
        from app.agent.memory import delete_dialog

        await delete_dialog("user1", "dlg1")

        mock_redis.delete.assert_awaited()
        assert fake_pg.sessions[0].executed  # DELETE ConversationHistory + Dialog
        assert fake_pg.sessions[0].committed
