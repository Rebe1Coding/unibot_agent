"""Tool: ask_clarification — request additional details from the student."""

from __future__ import annotations

import json

from langchain_core.tools import tool

# Sentinel prefix used to detect clarification responses in the agent output
CLARIFICATION_PREFIX = "__CLARIFICATION__"

# Маркер варианта «свой ответ» — интерфейс показывает поле свободного ввода.
OTHER_OPTION = {"label": "Свой вариант", "value": "__OTHER__", "free_text": True}


@tool
def ask_clarification(question: str, options: list[str]) -> str:
    """Задать студенту уточняющий вопрос с вариантами ответа.

    Используй этот инструмент, когда:
    - запрос недостаточно конкретен (не указан курс, группа, предмет)
    - запрос можно интерпретировать несколькими способами
    - есть разные способы решения задачи или варианты реализации кода

    Вариант «свой ответ» добавляется автоматически — перечисляй только
    содержательные варианты.

    ВАЖНО: После вызова этого инструмента ОБЯЗАТЕЛЬНО верни его результат
    как свой финальный ответ, без дополнительной обработки.

    Args:
        question: Уточняющий вопрос для студента.
        options: Список вариантов ответа (будут показаны как inline-кнопки).

    Returns:
        Сформатированный ответ с уточняющим вопросом.
    """
    clarification = {
        "question": question,
        # Свой вариант идёт последним, чтобы студент всегда мог ответить свободно.
        "options": [{"label": opt, "value": opt} for opt in options] + [OTHER_OPTION],
    }
    # Prefix signals to the agent loop that this is a clarification, not a final answer
    return f"{CLARIFICATION_PREFIX}{json.dumps(clarification, ensure_ascii=False)}"
