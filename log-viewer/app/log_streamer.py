from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import AsyncIterator

from docker.errors import DockerException, NotFound

from app.config import settings
from app.docker_client import get_container
from app.metrics import (
    active_streams,
    docker_errors_total,
    streamed_lines_total,
)

logger = logging.getLogger("log-viewer.streamer")

_SHUTDOWN = object()


def _parse_line(raw: bytes) -> tuple[str, str]:
    text = raw.decode("utf-8", errors="replace").rstrip("\n")
    if not text:
        return "", ""
    ts, sep, body = text.partition(" ")
    if not sep:
        return "", text
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return "", text
    return ts, body


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _run_stream(
    container_name: str,
    stream_kind: str,
    tail: int,
    since: int | None,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
    stop_event: threading.Event,
) -> None:
    try:
        container = get_container(container_name)
    except NotFound:
        docker_errors_total.labels(operation="get").inc()
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "error", "container": container_name, "error": "container not found"},
        )
        return
    except DockerException as exc:
        docker_errors_total.labels(operation="get").inc()
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "error", "container": container_name, "error": str(exc)},
        )
        return

    kwargs: dict = {
        "stream": True,
        "follow": True,
        "timestamps": True,
        "stdout": stream_kind == "stdout",
        "stderr": stream_kind == "stderr",
    }
    if since is not None:
        kwargs["since"] = since
    else:
        kwargs["tail"] = tail

    log_iter = None
    try:
        log_iter = container.logs(**kwargs)
        for chunk in log_iter:
            if stop_event.is_set():
                break
            for raw in chunk.splitlines():
                if not raw:
                    continue
                ts, body = _parse_line(raw)
                if not body:
                    continue
                event = {
                    "type": "log",
                    "ts": ts or datetime.now(timezone.utc).isoformat(),
                    "container": container_name,
                    "stream": stream_kind,
                    "text": body,
                }
                loop.call_soon_threadsafe(queue.put_nowait, event)
    except DockerException as exc:
        docker_errors_total.labels(operation="logs").inc()
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "error", "container": container_name, "error": str(exc)},
        )
    except Exception as exc:
        if not stop_event.is_set():
            logger.exception("Unexpected error streaming %s/%s", container_name, stream_kind)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "error", "container": container_name, "error": str(exc)},
            )
    finally:
        if log_iter is not None:
            try:
                log_iter.close()
            except Exception:
                pass


async def stream_logs(
    containers: list[str],
    tail: int,
    last_event_id: str | None = None,
) -> AsyncIterator[str]:
    if not containers:
        yield _sse("error", {"error": "no containers selected"})
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=settings.log_viewer_max_buffer)
    stop_event = threading.Event()
    threads: list[threading.Thread] = []

    since: int | None = None
    if last_event_id:
        try:
            since = int(last_event_id)
        except ValueError:
            since = None

    active_streams.inc()
    try:
        for name in containers:
            for kind in ("stdout", "stderr"):
                t = threading.Thread(
                    target=_run_stream,
                    args=(name, kind, tail, since, queue, loop, stop_event),
                    name=f"logstream-{name}-{kind}",
                    daemon=True,
                )
                t.start()
                threads.append(t)

        heartbeat_interval = settings.log_viewer_heartbeat_sec
        last_id = int(time.time())
        yield f"id: {last_id}\nretry: 3000\n" + _sse(
            "ready",
            {"containers": containers, "tail": tail, "ts": datetime.now(timezone.utc).isoformat()},
        )

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
            except asyncio.TimeoutError:
                last_id = int(time.time())
                yield f"id: {last_id}\n" + _sse(
                    "heartbeat",
                    {"ts": datetime.now(timezone.utc).isoformat()},
                )
                continue

            if event.get("type") == "error":
                yield _sse("error", {"container": event["container"], "error": event["error"]})
                continue

            streamed_lines_total.labels(
                container=event["container"], stream=event["stream"]
            ).inc()
            last_id = int(time.time())
            payload = {
                "ts": event["ts"],
                "container": event["container"],
                "stream": event["stream"],
                "text": event["text"],
            }
            yield f"id: {last_id}\n" + _sse("log", payload)
    finally:
        stop_event.set()
        active_streams.dec()
