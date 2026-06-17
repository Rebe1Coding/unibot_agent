"""Задача распознавания аудио. Режимы: command (только текст) и lecture (конспект в DOCX)."""

from __future__ import annotations

import base64
import io
import logging
from datetime import UTC, datetime, timedelta

import httpx
from minio import Minio
from minio.error import S3Error

from workers.celery_app import app
from workers.config import settings
from workers.tasks.audio_convert import to_supported
from workers.tasks.generate_doc import markdown_to_docx

logger = logging.getLogger(__name__)


def _get_minio_client() -> Minio:
    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def _chat(model: str, messages: list[dict], temperature: float = 0.0) -> str:
    """Запрос к RouterAI (OpenAI-совместимый /chat/completions). Возвращает текст ответа."""
    resp = httpx.post(
        f"{settings.routerai_base_url}/chat/completions",
        headers={"Authorization": f"Bearer {settings.routerai_api_key}"},
        json={"model": model, "messages": messages, "temperature": temperature},
        timeout=300.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _transcribe(audio_bytes: bytes, fmt: str) -> str:
    """Аудио → текст через аудио-LLM (Voxtral): передаём звук как input_audio."""
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "input_audio", "input_audio": {"data": audio_b64, "format": fmt}},
                {"type": "text", "text": "Распознай речь дословно. Верни только текст без комментариев."},
            ],
        }
    ]
    return _chat(settings.transcribe_model, messages).strip()


def _structure_lecture(transcript: str) -> str:
    """Сырой транскрипт → конспект в Markdown. При сбое возвращает исходный текст."""
    try:
        return _chat(
            settings.routerai_model,
            [
                {
                    "role": "system",
                    "content": (
                        "Ты — помощник студента. Структурируй транскрипцию лекции "
                        "в конспект с заголовками, ключевыми понятиями и списками. "
                        "Используй Markdown. Язык — русский."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            temperature=0.3,
        )
    except Exception:
        logger.exception("LLM недоступен, используем сырой транскрипт")
        return transcript


def _save_docx(minio_client: Minio, user_id: str, markdown_text: str) -> str:
    """Конспект → DOCX в MinIO. Возвращает presigned-ссылку на 24 часа."""
    docx_bytes = markdown_to_docx(markdown_text)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    object_name = f"documents/{user_id}/lecture_{timestamp}.docx"
    minio_client.put_object(
        bucket_name=settings.minio_bucket,
        object_name=object_name,
        data=io.BytesIO(docx_bytes),
        length=len(docx_bytes),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    return minio_client.presigned_get_object(
        settings.minio_bucket, object_name, expires=timedelta(hours=24)
    )


@app.task(name="app.worker.transcribe_audio", bind=True, max_retries=2)
def transcribe_audio(self, user_id: str, object_name: str, mode: str = "command") -> dict:
    logger.info("Распознавание: user_id=%s, object=%s, mode=%s", user_id, object_name, mode)

    minio_client = _get_minio_client()
    try:
        response = minio_client.get_object(settings.minio_bucket, object_name)
        audio_bytes = response.read()
        response.close()
        response.release_conn()
    except S3Error as exc:
        logger.error("Аудиофайл не найден в MinIO: %s — %s", object_name, exc)
        return {"status": "error", "user_id": user_id, "message": "Аудиофайл не найден"}

    # Нормализуем аудио в поддерживаемый формат; при сбое — исходный формат по расширению.
    audio_bytes, fmt = to_supported(audio_bytes)
    if not fmt:
        fmt = object_name.rsplit(".", 1)[-1] if "." in object_name else "ogg"
    try:
        transcript = _transcribe(audio_bytes, fmt)
    except httpx.HTTPError as exc:
        logger.warning("Сервис распознавания недоступен, retry: %s", exc)
        raise self.retry(exc=exc, countdown=30) from exc

    logger.info("Транскрипт получен: %d символов", len(transcript))

    # Короткое обращение — отдаём текст агенту как есть.
    if mode != "lecture":
        return {"status": "completed", "user_id": user_id, "transcript": transcript}

    # Лекция — структурируем и собираем DOCX.
    markdown_text = _structure_lecture(transcript)
    download_url = _save_docx(minio_client, user_id, markdown_text)
    logger.info("Конспект готов для user_id=%s", user_id)
    return {
        "status": "completed",
        "user_id": user_id,
        "transcript": markdown_text[:500],
        "download_url": download_url,
    }
