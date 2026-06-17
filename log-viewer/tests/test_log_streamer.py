from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from app import log_streamer
from app.log_streamer import _parse_line, _sse, stream_logs


def test_parse_line_with_timestamp():
    raw = b"2026-05-15T12:34:56.789Z hello world"
    ts, body = _parse_line(raw)
    assert ts == "2026-05-15T12:34:56.789Z"
    assert body == "hello world"


def test_parse_line_without_timestamp():
    raw = b"plain message without ts"
    ts, body = _parse_line(raw)
    assert ts == ""
    assert body == "plain message without ts"


def test_parse_line_empty():
    ts, body = _parse_line(b"")
    assert ts == ""
    assert body == ""


def test_sse_format():
    out = _sse("log", {"a": 1})
    assert out.startswith("event: log\n")
    assert "data: " in out
    assert out.endswith("\n\n")


@pytest.mark.asyncio
async def test_stream_logs_empty_containers():
    chunks = []
    async for chunk in stream_logs([], tail=10):
        chunks.append(chunk)
    assert len(chunks) == 1
    assert "no containers selected" in chunks[0]


@pytest.mark.asyncio
async def test_stream_logs_emits_ready_and_heartbeat(monkeypatch):
    container = MagicMock()
    container.logs.return_value = iter([])

    monkeypatch.setattr(log_streamer, "get_container", lambda name: container)
    from app import config
    monkeypatch.setattr(config.settings, "log_viewer_heartbeat_sec", 0.3)

    received = []
    gen = stream_logs(["agent"], tail=10)

    async def collect():
        async for chunk in gen:
            received.append(chunk)
            if sum("event: heartbeat" in c for c in received) >= 1 and any(
                "event: ready" in c for c in received
            ):
                break

    await asyncio.wait_for(collect(), timeout=5.0)
    assert any("event: ready" in c for c in received)
    assert any("event: heartbeat" in c for c in received)


@pytest.mark.asyncio
async def test_stream_logs_yields_log_event(monkeypatch):
    container = MagicMock()
    container.logs.side_effect = lambda **kw: (
        iter([b"2026-05-15T12:34:56.000Z hello"]) if kw.get("stdout") else iter([])
    )

    monkeypatch.setattr(log_streamer, "get_container", lambda name: container)
    from app import config
    monkeypatch.setattr(config.settings, "log_viewer_heartbeat_sec", 5)

    received = []
    gen = stream_logs(["agent"], tail=10)

    async def collect():
        async for chunk in gen:
            received.append(chunk)
            if any("event: log" in c for c in received):
                break

    await asyncio.wait_for(collect(), timeout=2.0)
    log_chunks = [c for c in received if "event: log" in c]
    assert log_chunks
    data_line = next(line for line in log_chunks[0].split("\n") if line.startswith("data: "))
    payload = json.loads(data_line[len("data: "):])
    assert payload["container"] == "agent"
    assert payload["stream"] == "stdout"
    assert payload["text"] == "hello"


@pytest.mark.asyncio
async def test_stream_logs_handles_container_not_found(monkeypatch):
    from docker.errors import NotFound

    def raise_not_found(name):
        raise NotFound("nope")

    monkeypatch.setattr(log_streamer, "get_container", raise_not_found)
    from app import config
    monkeypatch.setattr(config.settings, "log_viewer_heartbeat_sec", 5)

    received = []
    gen = stream_logs(["ghost"], tail=10)

    async def collect():
        async for chunk in gen:
            received.append(chunk)
            if any("event: error" in c for c in received):
                break

    await asyncio.wait_for(collect(), timeout=2.0)
    assert any("event: error" in c and "container not found" in c for c in received)
