"""FastAPI application — university agent core service."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from prometheus_client import generate_latest
from starlette.responses import Response, StreamingResponse

from app.logging_config import setup_logging
from app.metrics import (
    active_requests,
    chat_latency,
    chat_requests_total,
    voice_requests_total,
)
from app.middleware.auth import APIKeyMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    Clarification,
    ClarificationOption,
    DialogInfo,
    DialogListResponse,
    HealthResponse,
    HistoryMessage,
    HistoryResponse,
    NewDialogRequest,
    ServiceHealth,
    Source,
    VoiceResponse,
    VoiceStatusResponse,
)

logger = logging.getLogger(__name__)

# ── Logging configuration ────────────────────────────────────────────────────

setup_logging()


# ── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down external service connections."""
    from app.services import minio_service, postgres_service, qdrant_service, redis_service

    # Startup
    logger.info("Starting university-agent service...")
    try:
        await postgres_service.init_db()
    except Exception:
        logger.warning("PostgreSQL init failed — will retry on first request", exc_info=True)

    try:
        qdrant_service.ensure_collections()
    except Exception:
        logger.warning("Qdrant collection init failed", exc_info=True)

    try:
        minio_service.ensure_bucket()
    except Exception:
        logger.warning("MinIO bucket init failed", exc_info=True)

    logger.info("Service started")
    yield

    # Shutdown
    logger.info("Shutting down...")
    await redis_service.close_redis()
    await postgres_service.close_db()
    qdrant_service.close_qdrant()
    from app.services import embedding_service

    embedding_service.shutdown_executor()
    logger.info("Shutdown complete")


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="University Agent API",
    version="0.1.0",
    description="RAG + ReAct AI-агент для информационной поддержки студентов",
    lifespan=lifespan,
)

app.add_middleware(APIKeyMiddleware)
app.add_middleware(RequestIDMiddleware)


GUARDRAIL_MESSAGE = (
    "Извините, я могу помочь только с вопросами об учёбе в университете. Пожалуйста, переформулируйте ваш вопрос."
)


async def _prepare_request(request: ChatRequest):
    """Общая подготовка запроса для /chat и /chat/stream.

    Возвращает (user_input, chat_history) либо None, если запрос заблокирован гардрейлом.
    """
    from app.agent import memory
    from app.agent.guardrails import check_injection

    if check_injection(request.message):
        logger.warning("Prompt injection attempt from user=%s", request.user_id)
        return None

    user_input = request.message
    if request.clarification_response:
        user_input = f"{request.message}\n\nОтвет на уточняющий вопрос: {request.clarification_response}"

    chat_history = await memory.load_history(request.user_id, request.dialog_id)
    return user_input, chat_history


# ── POST /api/chat ───────────────────────────────────────────────────────────


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a text query through the ReAct agent pipeline."""
    from app.agent import memory, react_agent

    active_requests.inc()
    start = time.monotonic()

    user_id = request.user_id
    dialog_id = request.dialog_id
    message = request.message

    try:
        prepared = await _prepare_request(request)
        if prepared is None:
            return ChatResponse(answer=GUARDRAIL_MESSAGE)
        user_input, chat_history = prepared

        # ── Invoke agent ─────────────────────────────────────────────────
        try:
            result = await react_agent.invoke(user_input, chat_history, user_id=user_id)
        except Exception as e:
            logger.exception("Agent invocation failed for user=%s", user_id)
            raise HTTPException(status_code=500, detail="Ошибка обработки запроса") from e

        # ── Build response ───────────────────────────────────────────────
        clarification = None
        if result.clarification:
            clarification = Clarification(
                question=result.clarification["question"],
                options=[
                    ClarificationOption(
                        label=opt["label"],
                        value=opt["value"],
                        free_text=opt.get("free_text", False),
                    )
                    for opt in result.clarification.get("options", [])
                ],
            )

        sources = [
            Source(
                title=s.get("title", ""),
                url=s.get("url"),
                snippet=s.get("snippet"),
            )
            for s in result.sources
        ]

        response = ChatResponse(
            answer=result.answer,
            sources=sources,
            files=result.files,
            clarification=clarification,
        )

        # ── Save conversation turn ───────────────────────────────────────
        await memory.save_turn(user_id, dialog_id, message, result.answer)

        chat_requests_total.labels(status="success").inc()
        return response

    except Exception:
        chat_requests_total.labels(status="error").inc()
        raise
    finally:
        chat_latency.observe(time.monotonic() - start)
        active_requests.dec()


# ── POST /api/chat/stream ────────────────────────────────────────────────────


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream the ReAct pipeline as Server-Sent Events (tokens + tool activity)."""
    from app.agent import memory
    from app.agent.streaming import format_sse, stream

    user_id = request.user_id
    dialog_id = request.dialog_id
    message = request.message

    async def event_source():
        active_requests.inc()
        start = time.monotonic()
        try:
            yield format_sse({"type": "start"})

            prepared = await _prepare_request(request)
            if prepared is None:
                yield format_sse({"type": "token", "text": GUARDRAIL_MESSAGE})
                yield format_sse(
                    {"type": "done", "answer": GUARDRAIL_MESSAGE, "sources": [], "files": [], "clarification": None}
                )
                return
            user_input, chat_history = prepared

            done = None
            async for ev in stream(user_input, chat_history, user_id=user_id):
                if ev.get("type") == "done":
                    done = ev
                yield format_sse(ev)

            if done is not None:
                answer = done.get("answer", "")
                await memory.save_turn(user_id, dialog_id, message, answer)

            chat_requests_total.labels(status="success").inc()
        except Exception:
            logger.exception("Streaming chat failed for user=%s", user_id)
            chat_requests_total.labels(status="error").inc()
            yield format_sse({"type": "error", "message": "Ошибка обработки запроса"})
        finally:
            chat_latency.observe(time.monotonic() - start)
            active_requests.dec()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── POST /api/voice ──────────────────────────────────────────────────────────

MAX_AUDIO_BYTES = 25 * 1024 * 1024
ALLOWED_AUDIO_EXTS = {"ogg", "mp3", "wav", "m4a"}


@app.post("/api/voice", response_model=VoiceResponse)
async def voice(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    mode: str = Form("command"),
):
    """Upload an audio file for async transcription via Celery.

    The actual transcription is handled by a Celery worker in a separate container.
    This endpoint saves the file to MinIO and enqueues the task.
    """
    from app.services import minio_service

    # Читаем по частям и обрываем загрузку, как только превышен лимит размера
    audio_bytes = b""
    while chunk := await file.read(1024 * 1024):
        audio_bytes += chunk
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            voice_requests_total.labels(status="error").inc()
            raise HTTPException(status_code=413, detail="Аудиофайл слишком большой")

    # Расширение — только из белого списка, иначе ogg по умолчанию
    ext = "ogg"
    if file.filename and "." in file.filename:
        candidate = file.filename.rsplit(".", 1)[-1].lower()
        if candidate in ALLOWED_AUDIO_EXTS:
            ext = candidate
    import uuid as _uuid

    safe_name = _uuid.uuid4().hex[:12]
    object_name = f"audio/{user_id}/{safe_name}.{ext}"

    try:
        await minio_service.upload_bytes_async(
            object_name=object_name,
            data=audio_bytes,
            content_type=file.content_type or "audio/ogg",
        )
    except Exception as e:
        logger.exception("Failed to upload audio for user=%s", user_id)
        voice_requests_total.labels(status="error").inc()
        raise HTTPException(status_code=500, detail="Не удалось сохранить аудио") from e

    # Enqueue Celery task (the worker is in a separate container)
    # Воркер слушает очередь "default" — явно указываем её, иначе задача уйдёт в "celery" и зависнет
    try:
        from app.services.celery_client import get_celery

        task = get_celery().send_task(
            "app.worker.transcribe_audio",
            args=[user_id, object_name, mode],
            queue="default",
        )
        task_id = task.id
    except Exception as e:
        logger.exception("Failed to enqueue transcribe task for user=%s", user_id)
        voice_requests_total.labels(status="error").inc()
        raise HTTPException(status_code=503, detail="Очередь задач недоступна") from e

    voice_requests_total.labels(status="success").inc()
    return VoiceResponse(task_id=task_id, status="processing")


# ── GET /api/voice/{task_id} ────────────────────────────────────────────────


@app.get("/api/voice/{task_id}", response_model=VoiceStatusResponse)
async def voice_status(task_id: str):
    # Проверяем статус Celery-задачи транскрибации; результат содержит markdown_text и presigned_url
    try:
        from app.services.celery_client import get_celery
    except Exception as e:
        logger.exception("Celery client init failed")
        raise HTTPException(status_code=503, detail="Celery недоступен") from e

    try:
        async_result = get_celery().AsyncResult(task_id)
        state = async_result.state
    except Exception as e:
        logger.exception("Failed to query Celery task state: %s", task_id)
        raise HTTPException(status_code=503, detail="Не удалось получить статус задачи") from e

    if state in ("PENDING", "STARTED", "RETRY", "RECEIVED"):
        return VoiceStatusResponse(status="processing")

    if state == "FAILURE":
        err = str(async_result.info) if async_result.info else "task failed"
        return VoiceStatusResponse(status="error", error=err[:300])

    if state == "SUCCESS":
        result = async_result.result or {}
        # Воркер возвращает {"status": ..., "transcript": ..., "download_url": ...}
        if isinstance(result, dict):
            if result.get("status") == "error":
                return VoiceStatusResponse(status="error", error=result.get("message", "error"))
            text = result.get("transcript") or result.get("text") or ""
            return VoiceStatusResponse(
                status="completed", text=text, download_url=result.get("download_url")
            )
        return VoiceStatusResponse(status="completed", text=str(result))

    return VoiceStatusResponse(status="processing")


# ── Dialogs ──────────────────────────────────────────────────────────────────

# Допущение: сервис закрыт общим ключом INTERNAL_API_KEY и доступен только из
# доверенного контура (фронт за Nginx), который и подставляет user_id. Личности
# пользователя внутри сервиса нет, сверять user_id из пути не с чем. Если появится
# аутентификация на уровне пользователя — здесь нужно сверять владельца диалога.


@app.get("/api/dialogs/{user_id}", response_model=DialogListResponse)
async def list_dialogs(user_id: str):
    """List the user's dialogs, most recently updated first."""
    from app.agent import memory

    dialogs = await memory.list_dialogs(user_id)
    return DialogListResponse(
        user_id=user_id, dialogs=[DialogInfo(**d) for d in dialogs]
    )


@app.post("/api/dialogs/{user_id}", response_model=DialogInfo)
async def new_dialog(user_id: str, request: NewDialogRequest):
    """Create a new dialog; archive the previous one's Redis session (1h TTL)."""
    from app.agent import memory

    created = await memory.create_dialog(user_id, request.previous_dialog_id)
    return DialogInfo(**created)


@app.get("/api/dialogs/{user_id}/{dialog_id}", response_model=HistoryResponse)
async def dialog_history(user_id: str, dialog_id: str):
    """Retrieve the message log of a specific dialog (for switching)."""
    from app.agent import memory

    messages = await memory.dialog_messages(user_id, dialog_id)
    return HistoryResponse(
        user_id=user_id,
        messages=[HistoryMessage(role=m["role"], content=m["content"]) for m in messages],
    )


@app.delete("/api/dialogs/{user_id}/{dialog_id}")
async def delete_dialog(user_id: str, dialog_id: str):
    """Delete a dialog and its messages."""
    from app.agent import memory

    try:
        await memory.delete_dialog(user_id, dialog_id)
    except Exception as e:
        logger.exception("Failed to delete dialog=%s user=%s", dialog_id, user_id)
        raise HTTPException(status_code=500, detail="Не удалось удалить диалог") from e
    return {"status": "ok", "dialog_id": dialog_id}


# ── GET /health ──────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint for monitoring and orchestration."""
    from app.services import minio_service, postgres_service, qdrant_service, redis_service

    checks: dict[str, ServiceHealth] = {}

    # Redis
    t0 = time.monotonic()
    redis_ok = await redis_service.ping()
    checks["redis"] = ServiceHealth(
        status="ok" if redis_ok else "error",
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
    )

    # PostgreSQL
    t0 = time.monotonic()
    pg_ok = await postgres_service.ping()
    checks["postgres"] = ServiceHealth(
        status="ok" if pg_ok else "error",
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
    )

    # Qdrant
    t0 = time.monotonic()
    qdrant_ok = qdrant_service.ping()
    checks["qdrant"] = ServiceHealth(
        status="ok" if qdrant_ok else "error",
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
    )

    # MinIO
    t0 = time.monotonic()
    minio_ok = minio_service.ping()
    checks["minio"] = ServiceHealth(
        status="ok" if minio_ok else "error",
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
    )

    all_ok = all(c.status == "ok" for c in checks.values())
    return HealthResponse(
        status="ok" if all_ok else "degraded",
        services=checks,
    )


# ── GET /metrics ────────────────────────────────────────────────────────────


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
