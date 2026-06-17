"""Быстрый классификатор запросов: один короткий вызов LLM определяет тип запроса.

Тип передаётся агенту как направляющая подсказка (см. ``build_routing_hint``),
сам агент по-прежнему сам выбирает инструменты.
"""

from __future__ import annotations

import logging

from app.agent.prompts import CODE_GUIDELINES

logger = logging.getLogger(__name__)

# Допустимые типы запроса; mixed — безопасный запасной вариант (поиск + LLM).
QUERY_TYPES = ("factual", "code", "mixed", "unclear")
_FALLBACK = "mixed"

_CLASSIFIER_PROMPT = (
    "Определи тип запроса студента и ответь ОДНИМ словом без пояснений.\n"
    "factual — фактический вопрос об учёбе, факультете, преподавателях, литературе.\n"
    "code — просьба написать или объяснить код.\n"
    "mixed — нужен и факт из базы знаний, и написание кода/решение.\n"
    "unclear — запрос неясен или допускает несколько толкований.\n"
    "Запрос: {query}\n"
    "Тип:"
)

# Подсказки агенту по типу запроса (граф знаний планируется — пока поиск идёт в Qdrant).
_HINTS = {
    "factual": (
        "Тип запроса: фактический. Найди ответ через инструменты поиска по базе "
        "знаний (search_knowledge_base, search_literature) и отвечай строго по "
        "найденному, указывая источники."
    ),
    "code": (
        "Тип запроса: написание кода. Можешь опираться на свои знания без "
        "обязательного поиска, учитывая контекст вуза и факультета. Если есть "
        "несколько вариантов реализации — вызови ask_clarification.\n\n"
        f"{CODE_GUIDELINES}"
    ),
    "mixed": (
        "Тип запроса: смешанный. Сначала извлеки нужный контекст через "
        "search_knowledge_base, затем используй его при написании ответа или кода.\n\n"
        f"{CODE_GUIDELINES}"
    ),
    "unclear": (
        "Тип запроса: неясный. Вызови ask_clarification с вариантами и сразу "
        "верни его результат как финальный ответ, не угадывай."
    ),
}

_llm = None


def _get_llm():
    """Лёгкий клиент LLM для классификации (та же модель, короткий ответ)."""
    global _llm
    if _llm is None:
        from langchain_openai import ChatOpenAI

        from app.config import settings

        _llm = ChatOpenAI(
            model=settings.routerai_model,
            api_key=settings.routerai_api_key,
            base_url=settings.routerai_base_url,
            temperature=0,
            max_tokens=8,
            max_retries=1,
            request_timeout=10,
        )
    return _llm


async def classify(query: str) -> str:
    """Определить тип запроса; при ошибке вернуть безопасный mixed."""
    try:
        message = await _get_llm().ainvoke(_CLASSIFIER_PROMPT.format(query=query[:1000]))
        raw = (getattr(message, "content", "") or "").strip().lower()
    except Exception:
        logger.warning("Классификатор недоступен, использую запасной тип '%s'", _FALLBACK)
        return _FALLBACK
    for qtype in QUERY_TYPES:
        if qtype in raw:
            logger.info("Тип запроса: %s", qtype)
            return qtype
    logger.info("Тип запроса не распознан (%r), использую '%s'", raw, _FALLBACK)
    return _FALLBACK


def build_routing_hint(query_type: str) -> str:
    """Собрать направляющую подсказку для агента по типу запроса."""
    return _HINTS.get(query_type, _HINTS[_FALLBACK])
