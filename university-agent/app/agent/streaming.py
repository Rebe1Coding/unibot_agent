"""Потоковый прогон агента: перевод событий LangChain в события протокола SSE.

Протокол событий (поле ``type``):

- ``start``      — поток открыт;
- ``thinking``   — внутреннее размышление агента (до финального ответа);
- ``tool_start`` — агент начал использовать инструмент;
- ``tool_end``   — инструмент вернул результат (источники, файлы);
- ``token``      — очередной фрагмент текста ответа;
- ``done``       — финальный ответ целиком (источники, файлы, уточнение);
- ``error``      — ошибка обработки.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import BaseMessage

from app.agent import react_agent
from app.tools.ask_clarification import CLARIFICATION_PREFIX

logger = logging.getLogger(__name__)

# Инструмент размышления обрабатывается отдельно (событие ``thinking``), а не как
# обычный шаг с инструментом.
THINK_TOOL = "think"

# Человекочитаемые названия инструментов для интерфейса
TOOL_LABELS = {
    "search_knowledge_base": "Поиск в базе знаний",
    "search_literature": "Поиск литературы",
    "ask_clarification": "Уточняющий вопрос",
    "search_web": "Поиск в интернете",
    "md_to_docx_convert": "Подготовка документа Word",
}


def format_sse(payload: dict[str, Any]) -> str:
    """Сериализовать событие в кадр Server-Sent Events."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _tool_label(name: str) -> str:
    return TOOL_LABELS.get(name, name)


def _tool_query(tool_input: Any) -> str:
    """Короткое описание аргументов инструмента для показа пользователю."""
    if isinstance(tool_input, dict):
        for key in ("query", "name", "text", "topic", "markdown"):
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:120]
        for value in tool_input.values():
            if isinstance(value, str) and value.strip():
                return value.strip()[:120]
        return ""
    if isinstance(tool_input, str):
        return tool_input.strip()[:120]
    return ""


def _coerce_observation(output: Any) -> str:
    """Привести результат инструмента (ToolMessage или строку) к строке."""
    content = getattr(output, "content", output)
    return content if isinstance(content, str) else str(content)


class AgentEventTranslator:
    """Переводит сырые события ``astream_events`` в события протокола SSE.

    Хранит финальный результат цепочки агента (``final_output``) для построения
    события ``done`` и подавляет потоковую выдачу служебного текста уточнения.
    """

    def __init__(self) -> None:
        self.final_output: dict[str, Any] | None = None
        self._answer_buffer = ""
        self._prefix_resolved = False
        self._clarification_mode = False

    def translate(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        """Преобразовать одно сырое событие в ноль или несколько событий SSE."""
        kind = event.get("event")
        if kind == "on_chat_model_stream":
            return self._on_token(event)
        if kind == "on_tool_start":
            if event.get("name") == THINK_TOOL:
                return self._on_think(event)
            return self._on_tool_start(event)
        if kind == "on_tool_end":
            if event.get("name") == THINK_TOOL:
                return []
            return self._on_tool_end(event)
        if kind == "on_chain_end":
            self._capture_final(event)
        return []

    def flush(self) -> list[dict[str, Any]]:
        """Отдать остаток короткого ответа, не дотянувшего до длины префикса."""
        if self._clarification_mode or self._prefix_resolved:
            return []
        text = self._answer_buffer
        self._answer_buffer = ""
        self._prefix_resolved = True
        if not text or text.startswith(CLARIFICATION_PREFIX):
            return []
        return [{"type": "token", "text": text}]

    # ── Обработчики событий ──────────────────────────────────────────────────

    def _on_token(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        chunk = event.get("data", {}).get("chunk")
        text = getattr(chunk, "content", "") if chunk is not None else ""
        if not isinstance(text, str) or not text:
            return []
        if self._clarification_mode:
            return []
        if self._prefix_resolved:
            return [{"type": "token", "text": text}]

        # Копим начало ответа, чтобы не показать пользователю служебный
        # префикс CLARIFICATION: — это не ответ, а сигнал об уточнении.
        self._answer_buffer += text
        if len(self._answer_buffer) < len(CLARIFICATION_PREFIX):
            return []

        self._prefix_resolved = True
        if self._answer_buffer.startswith(CLARIFICATION_PREFIX):
            self._clarification_mode = True
            return []
        flushed, self._answer_buffer = self._answer_buffer, ""
        return [{"type": "token", "text": flushed}]

    def _on_think(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        """Перевести вызов инструмента think в событие размышления."""
        tool_input = event.get("data", {}).get("input")
        thought = ""
        if isinstance(tool_input, dict):
            thought = tool_input.get("thought", "") or ""
        elif isinstance(tool_input, str):
            thought = tool_input
        thought = thought.strip()
        if not thought:
            return []
        return [{"type": "thinking", "text": thought}]

    def _on_tool_start(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        name = event.get("name", "")
        return [
            {
                "type": "tool_start",
                "tool": name,
                "label": _tool_label(name),
                "query": _tool_query(event.get("data", {}).get("input")),
            }
        ]

    def _on_tool_end(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        name = event.get("name", "")
        observation = _coerce_observation(event.get("data", {}).get("output"))

        if observation.startswith(CLARIFICATION_PREFIX):
            return [
                {
                    "type": "tool_end",
                    "tool": name,
                    "label": _tool_label(name),
                    "found": True,
                    "sources": [],
                    "files": [],
                }
            ]

        data = react_agent.parse_observation(observation)
        return [
            {
                "type": "tool_end",
                "tool": name,
                "label": _tool_label(name),
                "found": bool(data.get("found", True)) if data else True,
                "sources": react_agent.sources_from_observation(observation),
                "files": react_agent.files_from_observation(observation),
            }
        ]

    def _capture_final(self, event: dict[str, Any]) -> None:
        output = event.get("data", {}).get("output")
        if isinstance(output, dict) and "intermediate_steps" in output:
            self.final_output = output


def _build_done(final_output: dict[str, Any] | None) -> dict[str, Any]:
    """Собрать авторитетное событие ``done`` из финального результата агента."""
    raw_output = (final_output or {}).get("output", "") or ""
    steps = (final_output or {}).get("intermediate_steps", []) or []

    clarification = react_agent.extract_clarification(raw_output, steps)
    answer = clarification["question"] if clarification else raw_output
    return {
        "type": "done",
        "answer": answer,
        "sources": react_agent.extract_sources(steps),
        "files": react_agent.extract_files(steps),
        "clarification": clarification,
    }


async def stream(
    user_input: str,
    chat_history: list[BaseMessage],
    user_id: str = "unknown",
) -> AsyncIterator[dict[str, Any]]:
    """Прогнать агента и отдавать события протокола по мере их появления."""
    executor = await react_agent.get_agent()
    translator = AgentEventTranslator()

    # Классифицируем запрос и даём агенту направляющую подсказку.
    from app.agent import classifier

    query_type = await classifier.classify(user_input)
    routing_hint = classifier.build_routing_hint(query_type)

    logger.info(
        "Потоковый запрос агента: user=%s type=%s msg_len=%d history_msgs=%d",
        user_id,
        query_type,
        len(user_input),
        len(chat_history),
    )

    async for event in executor.astream_events(
        {"input": user_input, "chat_history": chat_history, "routing_hint": routing_hint},
        version="v2",
    ):
        for out in translator.translate(event):
            yield out

    for out in translator.flush():
        yield out
    yield _build_done(translator.final_output)
