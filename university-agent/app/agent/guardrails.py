"""Input/output guardrails for the AI agent."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Паттерны prompt injection (регистронезависимые)
_INJECTION_PATTERNS = [
    r"(?i)забудь\s+(все|предыдущие|свои)\s+(инструкции|правила|промпт)",
    r"(?i)игнорируй\s+(все|предыдущие|свои)\s+(инструкции|правила)",
    r"(?i)ignore\s+(all\s+)?(previous\s+)?instructions",
    r"(?i)forget\s+(all\s+)?(previous\s+)?(instructions|rules)",
    r"(?i)you\s+are\s+now\s+",
    r"(?i)act\s+as\s+(if|a|an)\s+",
    r"(?i)pretend\s+(you\s+are|to\s+be)",
    r"(?i)system\s*prompt",
    r"(?i)new\s+instructions?\s*:",
    r"(?i)override\s+(system|previous)",
    r"(?i)ты\s+теперь\s+",
    r"(?i)притворись\s+",
    r"(?i)представь\s+(себе\s+)?что\s+ты\s+",
    r"(?i)твой\s+(системный\s+)?промпт",
    r"(?i)покажи\s+(свои\s+)?(инструкции|промпт|правила)",
]


def check_injection(text: str) -> bool:
    """Return True if the text contains potential prompt injection patterns."""
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, text):
            logger.warning("Обнаружена попытка взлома промпта: pattern=%s", pattern)
            return True
    logger.debug("Guardrails пройдены: len=%d", len(text))
    return False
