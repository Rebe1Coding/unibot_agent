"""FastAPI application for UniBot knowledge base management."""

from __future__ import annotations

import json
import logging
import secrets
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from prometheus_client import Counter, Histogram, generate_latest
from pydantic import BaseModel
from starlette.responses import Response as StarletteResponse

from indexer.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="UniBot Indexer", version="0.1.0")

# Prometheus metrics
upload_requests_total = Counter(
    "indexer_upload_requests_total",
    "Total upload requests",
    ["collection", "status"],
)
upload_duration = Histogram(
    "indexer_upload_duration_seconds",
    "Upload processing duration",
    ["collection"],
)
chunks_indexed_total = Counter(
    "indexer_chunks_indexed_total",
    "Total chunks indexed",
    ["collection"],
)

security = HTTPBasic()

STATIC_DIR = Path(__file__).parent / "static"

ALLOWED_EXTENSIONS = {".html", ".htm", ".pdf", ".md", ".txt"}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint."""
    return StarletteResponse(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# ── Auth ────────────────────────────────────────────────────────────────────


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, settings.admin_username)
    correct_password = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ── Pages ───────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index(username: str = Depends(verify_credentials)):
    html_file = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


# ── API: Stats ──────────────────────────────────────────────────────────────


@app.get("/api/stats")
async def api_stats(username: str = Depends(verify_credentials)):
    from indexer.qdrant_client import get_stats

    try:
        return get_stats()
    except Exception as e:
        logger.exception("Failed to get stats")
        return JSONResponse(
            status_code=503,
            content={"error": f"Qdrant недоступен: {e}"},
        )


# ── API: Upload Knowledge ──────────────────────────────────────────────────


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/upload/knowledge")
async def upload_knowledge(
    request: Request,
    files: list[UploadFile] = File(...),
    username: str = Depends(verify_credentials),
):
    # Validate extensions upfront
    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Неподдерживаемый формат файла: {f.filename}. "
                f"Допустимые форматы: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

    # Read all file contents before streaming (UploadFile can't be read inside generator)
    file_data = []
    for f in files:
        content = await f.read()
        file_data.append((f.filename, content))

    async def generate() -> AsyncGenerator[str, None]:
        from indexer.chunker import chunk_documents
        from indexer.embedder import embed_documents, embed_documents_sparse
        from indexer.parsers import get_parser
        from indexer.qdrant_client import (
            KNOWLEDGE_BASE,
            make_point_id,
            upsert_batch,
        )

        total_files = len(file_data)
        all_chunks: list[dict] = []
        total_upserted = 0

        # Stage 1: Parse
        for i, (filename, content) in enumerate(file_data):
            yield _sse_event(
                "progress",
                {
                    "stage": "parsing",
                    "file": filename,
                    "current": i + 1,
                    "total": total_files,
                },
            )
            parser = get_parser(filename)
            if parser is None:
                yield _sse_event(
                    "error",
                    {
                        "message": f"Нет парсера для файла: {filename}",
                    },
                )
                continue
            try:
                docs = parser(filename, content)
            except Exception as e:
                yield _sse_event(
                    "error",
                    {
                        "message": f"Не удалось распарсить {filename}: {e}",
                    },
                )
                continue

            # Stage 2: Chunk
            chunks = chunk_documents(
                docs,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            all_chunks.extend(chunks)
            yield _sse_event(
                "progress",
                {
                    "stage": "chunking",
                    "chunks_created": len(all_chunks),
                },
            )

        if not all_chunks:
            yield _sse_event(
                "done",
                {
                    "files_processed": total_files,
                    "chunks_created": 0,
                    "points_upserted": 0,
                },
            )
            return

        # Stage 3: Embed + Upsert in batches
        total_chunks = len(all_chunks)
        batch_size = settings.batch_size

        for batch_start in range(0, total_chunks, batch_size):
            batch_end = min(batch_start + batch_size, total_chunks)
            batch = all_chunks[batch_start:batch_end]

            texts = [c["text"] for c in batch]
            yield _sse_event(
                "progress",
                {
                    "stage": "embedding",
                    "current": batch_end,
                    "total": total_chunks,
                },
            )
            try:
                vectors = embed_documents(texts)
                sparse_vectors = embed_documents_sparse(texts)
            except Exception as e:
                yield _sse_event(
                    "error",
                    {
                        "message": f"Ошибка embedding: {e}",
                    },
                )
                return

            ids = [
                make_point_id(
                    KNOWLEDGE_BASE,
                    c["metadata"]["source"],
                    c["metadata"]["chunk_index"],
                )
                for c in batch
            ]
            payloads = [
                {"text": c["text"], **{k: v for k, v in c["metadata"].items() if k != "chunk_index"}} for c in batch
            ]

            yield _sse_event(
                "progress",
                {
                    "stage": "upserting",
                    "current": batch_end,
                    "total": total_chunks,
                },
            )
            try:
                upsert_batch(KNOWLEDGE_BASE, ids, vectors, payloads, sparse_vectors=sparse_vectors)
                total_upserted += len(batch)
            except Exception as e:
                yield _sse_event(
                    "error",
                    {
                        "message": f"Ошибка загрузки в Qdrant: {e}",
                    },
                )
                return

        yield _sse_event(
            "done",
            {
                "files_processed": total_files,
                "chunks_created": total_chunks,
                "points_upserted": total_upserted,
            },
        )

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── API: Upload Literature ─────────────────────────────────────────────────


class BookEntry(BaseModel):
    title: str
    author: str
    course: int
    subject: str
    file_key: str


class LiteratureRequest(BaseModel):
    books: list[BookEntry]


@app.post("/api/upload/literature")
async def upload_literature(
    data: LiteratureRequest,
    username: str = Depends(verify_credentials),
):
    from indexer.embedder import embed_documents, embed_documents_sparse
    from indexer.qdrant_client import LITERATURE, make_point_id, upsert_batch

    books = data.books
    if not books:
        raise HTTPException(status_code=400, detail="Список книг пуст")

    texts = [f"{b.title}. {b.author}. Курс {b.course}. Предмет: {b.subject}" for b in books]

    try:
        vectors = embed_documents(texts)
        sparse_vectors = embed_documents_sparse(texts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка embedding: {e}") from e

    ids = [make_point_id(LITERATURE, b.file_key, 0) for b in books]
    payloads = [
        {
            "title": b.title,
            "author": b.author,
            "course": b.course,
            "subject": b.subject,
            "file_key": b.file_key,
        }
        for b in books
    ]

    try:
        upsert_batch(LITERATURE, ids, vectors, payloads, sparse_vectors=sparse_vectors)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки в Qdrant: {e}") from e

    return {"books_indexed": len(books)}


# ── API: Collection Management ─────────────────────────────────────────────


@app.delete("/api/collection/{name}")
async def clear_collection(name: str, username: str = Depends(verify_credentials)):
    from indexer.qdrant_client import ALLOWED_COLLECTIONS
    from indexer.qdrant_client import clear_collection as _clear

    if name not in ALLOWED_COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"Коллекция '{name}' не найдена")

    try:
        _clear(name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка очистки коллекции: {e}") from e

    return {"collection": name, "status": "cleared"}


@app.get("/api/collection/{name}/sample")
async def collection_sample(name: str, username: str = Depends(verify_credentials)):
    from indexer.qdrant_client import ALLOWED_COLLECTIONS, scroll_sample

    if name not in ALLOWED_COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"Коллекция '{name}' не найдена")

    try:
        return scroll_sample(name, limit=10)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка чтения коллекции: {e}") from e
