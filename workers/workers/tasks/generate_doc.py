"""Задача генерации Word-файла из Markdown по ГОСТу."""

from __future__ import annotations

import io
import logging
import uuid
from datetime import timedelta

from minio import Minio

from workers.celery_app import app
from workers.config import settings

logger = logging.getLogger(__name__)


def _get_minio_client() -> Minio:
    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def _get_presign_client() -> Minio:
    endpoint = settings.minio_public_endpoint or settings.minio_endpoint
    secure = settings.minio_public_secure if settings.minio_public_endpoint else settings.minio_secure
    return Minio(
        endpoint=endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=secure,
        region="us-east-1",
    )


def markdown_to_docx(md: str) -> bytes:
    """Convert Markdown to GOST-formatted .docx bytes using shared builder."""
    from shared.docx_builder import markdown_to_docx as _build

    return _build(md, depersonalize=False)  # Worker: без деперсонализации (лекции)


@app.task(
    name="app.worker.generate_document",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def generate_document(self, user_id: str, markdown_text: str, filename: str | None = None) -> dict:
    """Генерация Word-файла из Markdown и загрузка в MinIO."""
    logger.info("Генерация документа для user_id=%s", user_id)

    try:
        docx_bytes = markdown_to_docx(markdown_text)

        name = filename or uuid.uuid4().hex
        if not name.endswith(".docx"):
            name = f"{name}.docx"
        docx_object_name = f"documents/{user_id}/{name}"

        logger.info("Загрузка в MinIO: %s", docx_object_name)
        minio_client = _get_minio_client()
        minio_client.put_object(
            bucket_name=settings.minio_bucket,
            object_name=docx_object_name,
            data=io.BytesIO(docx_bytes),
            length=len(docx_bytes),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        presigned_url = _get_presign_client().presigned_get_object(
            settings.minio_bucket,
            docx_object_name,
            expires=timedelta(hours=24),
        )

        logger.info("Документ готов: %s", docx_object_name)
        return {
            "status": "completed",
            "download_url": presigned_url,
            "object_name": docx_object_name,
        }

    except Exception as exc:
        logger.exception(
            "generate_document failed for user_id=%s, retry %d/%d", user_id, self.request.retries, self.max_retries
        )
        raise self.retry(exc=exc) from exc
