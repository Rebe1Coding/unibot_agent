import pytest


pytestmark = pytest.mark.asyncio


async def test_index_returns_html(client):
    res = await client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "UniBot" in res.text


async def test_metrics_endpoint(client):
    res = await client.get("/metrics")
    assert res.status_code == 200
    body = res.text
    assert "webgui_requests_total" in body
    assert "webgui_request_latency_seconds" in body
    assert "webgui_active_users" in body


async def test_health_proxies_upstream(client, mock_upstream, configure_api_key):
    mock_upstream.get("/health").respond(
        200,
        json={"status": "ok", "services": {"redis": {"status": "ok", "latency_ms": 1.0}}},
    )
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


async def test_health_handles_upstream_failure(client, mock_upstream):
    mock_upstream.get("/health").mock(side_effect=Exception("boom"))
    res = await client.get("/health")
    assert res.status_code == 503
    assert res.json()["status"] == "degraded"


async def test_chat_forwards_api_key(client, mock_upstream, configure_api_key):
    route = mock_upstream.post("/api/chat").respond(
        200,
        json={"answer": "ok", "sources": [], "files": [], "clarification": None},
    )
    payload = {"user_id": "abc-1", "message": "Привет", "clarification_response": None}
    res = await client.post("/api/chat", json=payload)
    assert res.status_code == 200
    assert res.json()["answer"] == "ok"
    assert route.called
    sent = route.calls.last.request
    assert sent.headers.get("x-api-key") == "test-key"


async def test_history_forwards(client, mock_upstream, configure_api_key):
    mock_upstream.get("/api/history/abc-1").respond(
        200,
        json={"user_id": "abc-1", "messages": []},
    )
    res = await client.get("/api/history/abc-1")
    assert res.status_code == 200
    assert res.json()["user_id"] == "abc-1"


async def test_chat_upstream_error_returns_502(client, mock_upstream, configure_api_key):
    mock_upstream.post("/api/chat").mock(side_effect=Exception("connection refused"))
    res = await client.post(
        "/api/chat",
        json={"user_id": "abc-1", "message": "hi", "clarification_response": None},
    )
    assert res.status_code == 502


async def test_active_users_gauge_increments(client, mock_upstream, configure_api_key):
    mock_upstream.post("/api/chat").respond(
        200,
        json={"answer": "ok", "sources": [], "files": [], "clarification": None},
    )
    await client.post(
        "/api/chat",
        json={"user_id": "user-A", "message": "hi", "clarification_response": None},
    )
    await client.post(
        "/api/chat",
        json={"user_id": "user-B", "message": "hi", "clarification_response": None},
    )
    metrics = (await client.get("/metrics")).text
    assert "webgui_active_users" in metrics
