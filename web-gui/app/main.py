from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.auth import current_user
from app.auth import router as auth_router
from app.config import settings
from app.metrics import ActiveUserTracker, request_latency, requests_total

logger = logging.getLogger("web-gui")
logging.basicConfig(level=settings.log_level.upper())

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.tracker = ActiveUserTracker(settings.active_user_window_seconds)
    app.state.http = httpx.AsyncClient(
        base_url=settings.api_base_url,
        timeout=httpx.Timeout(settings.request_timeout, connect=10.0),
    )
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(title="UniBot Web GUI", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    endpoint = request.url.path
    method = request.method
    status = str(response.status_code)
    requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
    request_latency.labels(method=method, endpoint=endpoint).observe(elapsed)
    return response


@app.middleware("http")
async def require_auth(request: Request, call_next):
    """Gate /api/* behind a valid session cookie."""
    path = request.url.path
    if not path.startswith("/api") or settings.auth_disabled:
        return await call_next(request)
    if current_user(request) is None:
        return JSONResponse(status_code=401, content={"detail": "Не авторизован"})
    return await call_next(request)


def _user_id(request: Request) -> str:
    """Authenticated user id from the session cookie (server-side source of truth)."""
    user = current_user(request)
    if user:
        return user["sub"]
    if settings.auth_disabled:
        return "dev-user"
    raise HTTPException(status_code=401, detail="Не авторизован")


def _auth_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}
    if settings.api_key:
        headers["X-API-Key"] = settings.api_key
    rid = request.headers.get("x-request-id")
    if rid:
        headers["X-Request-ID"] = rid
    return headers


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html")


@app.get("/health")
async def health(request: Request) -> Response:
    client: httpx.AsyncClient = request.app.state.http
    try:
        upstream = await client.get("/health", timeout=10.0)
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )
    except httpx.HTTPError as exc:
        logger.warning("Upstream /health failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "error": str(exc), "services": {}},
        )


@app.get("/metrics")
async def metrics(request: Request) -> Response:
    request.app.state.tracker.refresh()
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Chat ─────────────────────────────────────────────────────────────────────


def _inject_user(payload: bytes, user_id: str) -> bytes:
    """Force the authenticated user_id into a chat JSON body."""
    try:
        body = json.loads(payload) if payload else {}
    except json.JSONDecodeError:
        body = {}
    body["user_id"] = user_id
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


@app.post("/api/chat")
async def proxy_chat(request: Request) -> Response:
    user_id = _user_id(request)
    request.app.state.tracker.touch(user_id)
    payload = _inject_user(await request.body(), user_id)
    return await _forward(request, "POST", "/api/chat", content=payload, json_body=True)


@app.post("/api/chat/stream")
async def proxy_chat_stream(request: Request) -> Response:
    user_id = _user_id(request)
    request.app.state.tracker.touch(user_id)
    payload = _inject_user(await request.body(), user_id)

    client: httpx.AsyncClient = request.app.state.http
    headers = _auth_headers(request)
    headers["Content-Type"] = "application/json"

    async def relay():
        # Без таймаута на чтение: SSE-поток живёт, пока агент думает и печатает.
        async with client.stream(
            "POST",
            "/api/chat/stream",
            content=payload,
            headers=headers,
            timeout=httpx.Timeout(settings.request_timeout, connect=10.0, read=None),
        ) as upstream:
            async for chunk in upstream.aiter_raw():
                yield chunk

    return StreamingResponse(
        relay(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Dialogs ──────────────────────────────────────────────────────────────────


@app.get("/api/dialogs")
async def proxy_list_dialogs(request: Request) -> Response:
    user_id = _user_id(request)
    return await _forward(request, "GET", f"/api/dialogs/{user_id}")


@app.post("/api/dialogs")
async def proxy_new_dialog(request: Request) -> Response:
    user_id = _user_id(request)
    payload = await request.body()
    return await _forward(request, "POST", f"/api/dialogs/{user_id}", content=payload, json_body=True)


@app.get("/api/dialogs/{dialog_id}")
async def proxy_dialog_history(request: Request, dialog_id: str) -> Response:
    user_id = _user_id(request)
    return await _forward(request, "GET", f"/api/dialogs/{user_id}/{dialog_id}")


@app.delete("/api/dialogs/{dialog_id}")
async def proxy_delete_dialog(request: Request, dialog_id: str) -> Response:
    user_id = _user_id(request)
    return await _forward(request, "DELETE", f"/api/dialogs/{user_id}/{dialog_id}")


# ── Voice ────────────────────────────────────────────────────────────────────


@app.post("/api/voice")
async def proxy_voice(request: Request, file: UploadFile, mode: str = "command") -> Response:
    user_id = _user_id(request)
    request.app.state.tracker.touch(user_id)
    client: httpx.AsyncClient = request.app.state.http
    data = await file.read()
    files = {"file": (file.filename, data, file.content_type or "application/octet-stream")}
    form = {"user_id": user_id, "mode": mode}
    try:
        upstream = await client.post(
            "/api/voice",
            data=form,
            files=files,
            headers=_auth_headers(request),
        )
    except httpx.HTTPError as exc:
        logger.warning("Upstream /api/voice failed: %s", exc)
        return JSONResponse(status_code=502, content={"detail": f"Upstream error: {exc}"})
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )


@app.get("/api/voice/{task_id}")
async def proxy_voice_status(request: Request, task_id: str) -> Response:
    return await _forward(request, "GET", f"/api/voice/{task_id}")


async def _forward(
    request: Request,
    method: str,
    path: str,
    *,
    content: bytes | None = None,
    json_body: bool = False,
) -> Response:
    client: httpx.AsyncClient = request.app.state.http
    headers = _auth_headers(request)
    if json_body:
        headers["Content-Type"] = "application/json"
    try:
        upstream = await client.request(method, path, content=content, headers=headers)
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"detail": "Upstream timeout"},
        )
    except httpx.HTTPError as exc:
        logger.warning("Upstream %s %s failed: %s", method, path, exc)
        return JSONResponse(status_code=502, content={"detail": f"Upstream error: {exc}"})
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
