from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from docker.errors import DockerException
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import settings
from app.docker_client import list_project_containers, ping
from app.log_streamer import stream_logs
from app.metrics import request_latency, requests_total

logger = logging.getLogger("log-viewer")
logging.basicConfig(level=settings.log_viewer_log_level.upper())

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="UniBot Log Viewer", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    endpoint = request.url.path
    requests_total.labels(method=request.method, endpoint=endpoint, status=str(response.status_code)).inc()
    request_latency.labels(method=request.method, endpoint=endpoint).observe(elapsed)
    return response


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html")


@app.get("/health")
async def health() -> Response:
    docker_ok = ping()
    status_code = 200 if docker_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if docker_ok else "degraded",
            "docker": "ok" if docker_ok else "unavailable",
        },
    )


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/containers")
async def api_containers() -> JSONResponse:
    try:
        items = list_project_containers()
    except DockerException as exc:
        raise HTTPException(status_code=503, detail=f"Docker unavailable: {exc}") from exc
    return JSONResponse(content={"containers": items})


@app.get("/api/logs/stream")
async def api_logs_stream(
    request: Request,
    containers: str = Query(..., description="Comma-separated container names"),
    tail: int = Query(default=settings.log_viewer_default_tail, ge=0, le=10000),
) -> StreamingResponse:
    names = [c.strip() for c in containers.split(",") if c.strip()]
    if not names:
        raise HTTPException(status_code=400, detail="containers query param is empty")

    last_event_id = request.headers.get("Last-Event-ID")

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(
        stream_logs(names, tail=tail, last_event_id=last_event_id),
        media_type="text/event-stream",
        headers=headers,
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
