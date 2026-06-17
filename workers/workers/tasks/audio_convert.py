"""Нормализация аудио в формат, понятный модели распознавания (ogg/opus, 16 кГц моно)."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

TARGET_FORMAT = "ogg"


def to_supported(audio_bytes: bytes) -> tuple[bytes, str]:
    """Любой формат → ogg/opus через ffmpeg. При сбое возвращает исходные байты."""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-i", "pipe:0",
                "-ac", "1", "-ar", "16000", "-c:a", "libopus",
                "-f", "ogg", "pipe:1",
            ],
            input=audio_bytes,
            capture_output=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout, TARGET_FORMAT
        logger.warning("ffmpeg вернул код %s: %s", result.returncode, result.stderr.decode("utf-8", "ignore")[:300])
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        logger.warning("ffmpeg недоступен, отправляем аудио без конвертации: %s", exc)
    return audio_bytes, ""
