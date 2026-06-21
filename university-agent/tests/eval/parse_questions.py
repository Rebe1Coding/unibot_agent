"""Парсер тестовых Markdown-файлов из tests/llm-judge/."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "llm-judge"

CATEGORY_MAP = {
    "01-relevant-rag.md": "Релевантный (RAG)",
    "02-reasoning.md": "На подумать",
    "03-off-topic.md": "Не по теме",
    "04-meta-provocative.md": "Провокационный/Мета",
    "05-stress-edge.md": "Стресс-кейс",
}


@dataclass
class TestQuestion:
    """Структура одного тестового вопроса."""

    id: int
    category: str
    subcategory: str  # из **Категория:** ...
    question: str
    expected_criteria: str  # из секции «Ожидаемый ответ / Критерии оценки»
    source_file: str
    raw_id: int = 0  # номер вопроса в исходном файле


@dataclass
class EvalResult:
    """Результат оценки одного вопроса."""

    question: TestQuestion
    agent_answer: str
    score: float
    reason: str
    error: str | None = None


def parse_all_questions() -> list[TestQuestion]:
    """Распарсить все вопросы из Markdown-файлов."""
    questions: list[TestQuestion] = []
    global_id = 0

    for filename in sorted(TEST_DIR.glob("*.md")):
        if filename.name == "README.md":
            continue
        questions.extend(_parse_file(filename, global_id))
        global_id = len(questions)

    return questions


def _parse_file(filepath: Path, start_id: int) -> list[TestQuestion]:
    """Распарсить один Markdown-файл с вопросами."""
    content = filepath.read_text(encoding="utf-8")
    category = CATEGORY_MAP.get(filepath.name, "Неизвестно")
    questions: list[TestQuestion] = []

    blocks = re.split(r"\n## Вопрос \d+:", content)
    blocks = [b.strip() for b in blocks if b.strip()]

    for i, block in enumerate(blocks):
        parts = re.split(r"\n\*\*Ожидаемый ответ / Критерии оценки:\*\*", block, maxsplit=1)
        if len(parts) < 2:
            continue

        header_body = parts[0].strip()
        criteria = parts[1].strip()

        # Извлечь **Категория:** и текст вопроса
        cat_match = re.search(r"\*\*Категория:\*\*\s*(.+?)$", header_body, re.MULTILINE)
        subcategory = cat_match.group(1).strip() if cat_match else ""

        # Всё после Категория: до следующей строки с ** — это вопрос
        # Упрощённо: убираем строку с **Категория:**, остальное — вопрос
        question_text = re.sub(r"\*\*Категория:\*\*\s*.+?$", "", header_body, flags=re.MULTILINE).strip()
        question_text = re.sub(r"\n\*\*Вопрос:\*\*\s*", "", question_text)

        question_text = _clean_question_text(question_text)

        if question_text.strip():
            questions.append(
                TestQuestion(
                    id=start_id + len(questions),
                    category=category,
                    subcategory=subcategory,
                    question=question_text,
                    expected_criteria=criteria,
                    source_file=filepath.name,
                    raw_id=i + 1,
                )
            )

    return questions


def _clean_question_text(text: str) -> str:
    """Очистить текст вопроса от лишних Markdown-артефактов."""
    # Убрать жирный текст-подсказку в скобках (например, "(Сгенерировать ~3000 слов...)")
    text = re.sub(r"\(Сгенерировать[^)]*\)", "", text)
    text = re.sub(r"\(Повторить[^)]*\)", "", text)
    # Убрать "(пустая строка)" как подсказку форматирования
    text = re.sub(r"\(пустая строка\)", "", text)

    # Убрать подсказки про флаги в начале вопросов
    # Убираем лишние пробелы и переносы
    text = text.strip()
    # Схлопнуть множественные переносы
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def group_by_category(
    questions: list[TestQuestion],
) -> dict[str, list[TestQuestion]]:
    """Сгруппировать вопросы по категориям."""
    groups: dict[str, list[TestQuestion]] = {}
    for q in questions:
        groups.setdefault(q.category, []).append(q)
    return groups
