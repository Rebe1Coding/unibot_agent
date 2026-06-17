"""Tool: md_to_docx_convert — convert Markdown to GOST-formatted .docx."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from langchain_core.tools import tool

from app.services import minio_service

logger = logging.getLogger(__name__)


@tool
async def md_to_docx_convert(markdown_text: str, filename: str | None = None) -> str:
    """Конвертировать Markdown-текст в Word-документ (.docx) по ГОСТу.

    Документ оформляется по стандартам:
    - ГОСТ 7.32-2017 (структура отчёта о НИР)
    - ГОСТ 2.105-2019 (оформление текстовых документов)

    Применяются: Times New Roman 14pt, полуторный интервал, абзацный отступ 1.25 см,
    поля (лево 3 / право 1 / верх-низ 2 см), нумерация страниц.

    Args:
        markdown_text: Текст в формате Markdown.
        filename: Имя выходного файла (без расширения). По умолчанию — UUID.

    Returns:
        JSON с ключом download_url — ссылка на скачивание файла из MinIO.
    """
    try:
        loop = asyncio.get_running_loop()
        docx_bytes = await loop.run_in_executor(None, _convert, markdown_text)
        name = filename or uuid.uuid4().hex
        object_name = f"documents/{name}.docx"

        await minio_service.upload_bytes_async(
            object_name=object_name,
            data=docx_bytes,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        url = await minio_service.presigned_url_async(object_name)

        return json.dumps(
            {"success": True, "download_url": url, "object_name": object_name},
            ensure_ascii=False,
        )
    except Exception as e:
        logger.exception("md_to_docx_convert failed")
        return json.dumps(
            {"success": False, "error": f"Ошибка конвертации: {e}"},
            ensure_ascii=False,
        )


# ── Internal conversion logic ────────────────────────────────────────────────


def _convert(md: str) -> bytes:
    """Convert Markdown to GOST-formatted .docx bytes using shared builder."""
    from shared.docx_builder import markdown_to_docx

    return markdown_to_docx(md, depersonalize=True)
