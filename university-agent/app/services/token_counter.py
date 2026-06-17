"""Token counting and history trimming to keep prompts within the model budget."""

from __future__ import annotations

import logging

from langchain_core.messages import BaseMessage

from app.config import CONTEXT_WINDOWS, settings

logger = logging.getLogger(__name__)

_DEFAULT_WINDOW = 128000
_PER_MESSAGE_OVERHEAD = 4

try:
    import tiktoken

    _ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover - tiktoken is optional
    _ENCODING = None
    logger.warning("tiktoken недоступен, использую эвристику chars/4 для подсчёта токенов")


def _model_name() -> str:
    return settings.routerai_model


def _text_of(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text", "")))
        return " ".join(parts)
    return str(content)


def _count_one(message: BaseMessage) -> int:
    text = _text_of(message)
    if _ENCODING is not None:
        return len(_ENCODING.encode(text)) + _PER_MESSAGE_OVERHEAD
    return len(text) // 4 + _PER_MESSAGE_OVERHEAD


def count_tokens(messages: list[BaseMessage]) -> int:
    """Approximate the total token count of a list of messages."""
    return sum(_count_one(m) for m in messages)


def context_window() -> int:
    """Resolve the model context window from config or the model name."""
    if settings.context_window > 0:
        return settings.context_window
    name = _model_name().lower()
    for fragment, window in CONTEXT_WINDOWS.items():
        if fragment in name:
            return window
    return _DEFAULT_WINDOW


def history_budget() -> int:
    """Token budget available for chat history (window * ratio - reserve)."""
    total = int(context_window() * settings.token_budget_ratio)
    return max(total - settings.token_reserve, 1000)


def trim_to_budget(messages: list[BaseMessage], budget: int) -> list[BaseMessage]:
    """Drop the oldest messages until the list fits within the token budget."""
    kept_reversed: list[BaseMessage] = []
    running = 0
    for message in reversed(messages):
        cost = _count_one(message)
        if kept_reversed and running + cost > budget:
            break
        running += cost
        kept_reversed.append(message)

    if len(kept_reversed) < len(messages):
        logger.info(
            "История обрезана по бюджету: budget=%d kept=%d dropped=%d",
            budget,
            len(kept_reversed),
            len(messages) - len(kept_reversed),
        )
    return list(reversed(kept_reversed))
