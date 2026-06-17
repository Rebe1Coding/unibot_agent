from __future__ import annotations

import logging
from threading import Lock
from typing import Any

import docker
from docker.errors import DockerException

from app.config import settings
from app.metrics import docker_errors_total

logger = logging.getLogger("log-viewer.docker")

_client: docker.DockerClient | None = None
_lock = Lock()

PROJECT_LABEL = "com.docker.compose.project"
SERVICE_LABEL = "com.docker.compose.service"


def get_client() -> docker.DockerClient:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = docker.from_env()
    return _client


def reset_client() -> None:
    global _client
    with _lock:
        _client = None


def ping() -> bool:
    try:
        return bool(get_client().ping())
    except DockerException as exc:
        docker_errors_total.labels(operation="ping").inc()
        logger.warning("Docker ping failed: %s", exc)
        return False


def list_project_containers() -> list[dict[str, Any]]:
    try:
        client = get_client()
        containers = client.containers.list(
            all=True,
            filters={"label": f"{PROJECT_LABEL}={settings.log_viewer_project_name}"},
        )
    except DockerException as exc:
        docker_errors_total.labels(operation="list").inc()
        logger.warning("Docker list failed: %s", exc)
        raise

    result: list[dict[str, Any]] = []
    for c in containers:
        labels = c.labels or {}
        result.append(
            {
                "id": c.short_id,
                "name": c.name,
                "service": labels.get(SERVICE_LABEL, c.name),
                "status": c.status,
                "image": (c.image.tags[0] if c.image.tags else c.image.short_id),
            }
        )
    result.sort(key=lambda x: x["name"])
    return result


def get_container(name_or_id: str):
    return get_client().containers.get(name_or_id)
