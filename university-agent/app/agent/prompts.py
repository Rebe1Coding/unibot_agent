"""Загрузка системного промпта и инструкций агента из внешних файлов.

Тексты вынесены в каталог ``instructions/`` и не хранятся в коде: рабочие файлы
``*.md`` добавлены в .gitignore (агент не должен раскрывать свои промпты), а в
репозитории лежат только примеры ``*.example.md``. Загрузчик берёт рабочий файл,
а при его отсутствии откатывается к примеру.
"""

from __future__ import annotations

from pathlib import Path

_INSTRUCTIONS_DIR = Path(__file__).resolve().parent / "instructions"


def _load(name: str) -> str:
    """Прочитать инструкцию ``name`` (рабочий файл или пример как запасной)."""
    real = _INSTRUCTIONS_DIR / f"{name}.md"
    example = _INSTRUCTIONS_DIR / f"{name}.example.md"
    path = real if real.exists() else example
    return path.read_text(encoding="utf-8").strip()


# Системный промпт — только ключевые правила поведения.
SYSTEM_PROMPT = _load("system")

# Подробные правила размышления (спецслучаи) — попадают в описание инструмента
# think, а не в системный промпт.
THINKING_GUIDELINES = "\n\n".join(_load(name) for name in ("safety", "abbreviations"))

# Правила написания кода — подмешиваются в подсказку классификатора для запросов
# типа code/mixed. Вынесены отдельным файлом, чтобы легко расширять.
CODE_GUIDELINES = _load("code")
