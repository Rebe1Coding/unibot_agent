import pytest
from docker.errors import DockerException


pytestmark = pytest.mark.asyncio


async def test_index_returns_html(client):
    res = await client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Log Viewer" in res.text


async def test_metrics_endpoint(client):
    res = await client.get("/metrics")
    assert res.status_code == 200
    body = res.text
    assert "logviewer_requests_total" in body
    assert "logviewer_active_streams" in body


async def test_health_ok(client, mock_docker):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "docker": "ok"}


async def test_health_degraded(client, mock_docker):
    mock_docker.ping.side_effect = DockerException("daemon down")
    res = await client.get("/health")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "degraded"
    assert body["docker"] == "unavailable"


async def test_containers_list(client):
    res = await client.get("/api/containers")
    assert res.status_code == 200
    payload = res.json()
    names = [c["name"] for c in payload["containers"]]
    assert names == sorted(names)
    assert "university-agent" in names
    assert "postgres" in names


async def test_containers_filters_by_project_label(client, mock_docker):
    await client.get("/api/containers")
    mock_docker.containers.list.assert_called_once()
    kwargs = mock_docker.containers.list.call_args.kwargs
    assert kwargs["filters"] == {"label": "com.docker.compose.project=unibot"}


async def test_containers_docker_failure(client, mock_docker):
    mock_docker.containers.list.side_effect = DockerException("daemon down")
    res = await client.get("/api/containers")
    assert res.status_code == 503


async def test_logs_stream_requires_containers(client):
    res = await client.get("/api/logs/stream?containers=")
    assert res.status_code == 400


async def test_logs_stream_validates_tail(client):
    res = await client.get("/api/logs/stream?containers=foo&tail=-1")
    assert res.status_code == 422
